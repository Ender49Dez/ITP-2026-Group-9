#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_PN532.h>
#include <ArduinoJson.h>

#define PN532_IRQ 4
#define PN532_RESET 5
#define NFC_START_PAGE 4
#define MAX_USER_PAGES 36

Adafruit_PN532 nfc(PN532_IRQ, PN532_RESET);

String serialBuffer;
bool pn532Ready = false;

void sendStatus(const char *status, const String &message, const String &payload = "");
void handleIncomingJson(const String &jsonLine);
bool waitForNfcTag(uint8_t *uid, uint8_t *uidLength, unsigned long timeoutMs);
bool writePayloadToTag(const String &payload);
bool buildNdefMessage(const String &payload, uint8_t *buffer, size_t *messageLength);
bool buildUriRecord(const String &url, uint8_t *record, size_t *recordLength);
bool buildTextRecord(const String &text, uint8_t *record, size_t *recordLength);

void setup() {
  Serial.begin(115200);
  delay(500);

  Wire.begin(21, 22);
  nfc.begin();

  uint32_t versionData = nfc.getFirmwareVersion();
  if (!versionData) {
    sendStatus("error", "PN532 module not detected. Check power, wiring, and I2C mode.");
    return;
  }

  nfc.SAMConfig();
  pn532Ready = true;

  sendStatus("ok", "ESP32 NFC receipt writer is ready.");
}

void loop() {
  while (Serial.available() > 0) {
    char incoming = static_cast<char>(Serial.read());

    if (incoming == '\n' || incoming == '\r') {
      if (serialBuffer.length() > 0) {
        handleIncomingJson(serialBuffer);
        serialBuffer = "";
      }
    } else {
      serialBuffer += incoming;
    }
  }
}

void handleIncomingJson(const String &jsonLine) {
  if (!pn532Ready) {
    sendStatus("error", "PN532 is not ready. Restart after checking the module.");
    return;
  }

  size_t jsonCapacity = (jsonLine.length() * 2) + 1024;
  DynamicJsonDocument request(jsonCapacity);
  DeserializationError parseError = deserializeJson(request, jsonLine);
  if (parseError) {
    sendStatus("error", String("Invalid JSON received from Python: ") + parseError.c_str());
    return;
  }

  const char *receiptId = request["receipt_id"];
  const char *receiptUrl = request["receipt_url"];
  const char *shopName = request["shop_name"];
  const char *receiptDate = request["date"];
  const char *receiptTime = request["time"];

  bool hasReceiptId = receiptId != nullptr && strlen(receiptId) > 0;
  bool hasReceiptUrl = receiptUrl != nullptr && strlen(receiptUrl) > 0;

  if (!hasReceiptId && !hasReceiptUrl) {
    sendStatus("error", "JSON must include receipt_id or receipt_url.");
    return;
  }

  String payload = hasReceiptUrl ? String(receiptUrl) : String(receiptId);

  Serial.println("Full receipt JSON received from Python.");
  if (shopName != nullptr) {
    Serial.print("Shop Name: ");
    Serial.println(shopName);
  }
  if (receiptDate != nullptr && receiptTime != nullptr) {
    Serial.print("Receipt Time: ");
    Serial.print(receiptDate);
    Serial.print(" ");
    Serial.println(receiptTime);
  }
  if (request["final_total"].is<float>() || request["final_total"].is<double>()) {
    Serial.print("Final Total: ");
    Serial.println(request["final_total"].as<float>(), 2);
  }

  sendStatus("pending", "Receipt received. Tap an NFC tag on the PN532 now.", payload);

  if (writePayloadToTag(payload)) {
    sendStatus("ok", "NFC write successful.", payload);
  } else {
    sendStatus("error", "Failed to write the receipt reference to the NFC tag.");
  }
}

bool waitForNfcTag(uint8_t *uid, uint8_t *uidLength, unsigned long timeoutMs) {
  unsigned long startTime = millis();

  while (millis() - startTime < timeoutMs) {
    if (nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, uidLength)) {
      return true;
    }
    delay(200);
  }

  return false;
}

bool writePayloadToTag(const String &payload) {
  uint8_t uid[7];
  uint8_t uidLength = 0;

  if (!waitForNfcTag(uid, &uidLength, 15000)) {
    sendStatus("error", "No NFC tag detected within 15 seconds.");
    return false;
  }

  uint8_t ndefMessage[160];
  size_t messageLength = 0;

  if (!buildNdefMessage(payload, ndefMessage, &messageLength)) {
    sendStatus("error", "Payload is too large for the configured NFC tag.");
    return false;
  }

  size_t requiredPages = (messageLength + 3) / 4;
  if (requiredPages > MAX_USER_PAGES) {
    sendStatus("error", "The NFC tag does not have enough writable pages.");
    return false;
  }

  for (size_t pageOffset = 0; pageOffset < requiredPages; ++pageOffset) {
    uint8_t pageData[4] = {0, 0, 0, 0};
    for (size_t byteIndex = 0; byteIndex < 4; ++byteIndex) {
      size_t sourceIndex = (pageOffset * 4) + byteIndex;
      if (sourceIndex < messageLength) {
        pageData[byteIndex] = ndefMessage[sourceIndex];
      }
    }

    if (!nfc.ntag2xx_WritePage(NFC_START_PAGE + pageOffset, pageData)) {
      return false;
    }
    delay(20);
  }

  return true;
}

bool buildNdefMessage(const String &payload, uint8_t *buffer, size_t *messageLength) {
  uint8_t record[150];
  size_t recordLength = 0;

  bool looksLikeUrl = payload.startsWith("http://") || payload.startsWith("https://");
  bool recordBuilt = looksLikeUrl
                         ? buildUriRecord(payload, record, &recordLength)
                         : buildTextRecord(payload, record, &recordLength);

  if (!recordBuilt) {
    return false;
  }

  size_t totalLength = recordLength + 3;
  if (totalLength > 160) {
    return false;
  }

  buffer[0] = 0x03;
  buffer[1] = static_cast<uint8_t>(recordLength);
  memcpy(buffer + 2, record, recordLength);
  buffer[2 + recordLength] = 0xFE;

  *messageLength = totalLength;
  return true;
}

bool buildUriRecord(const String &url, uint8_t *record, size_t *recordLength) {
  uint8_t prefixCode = 0x00;
  String remainingUrl = url;

  if (url.startsWith("https://")) {
    prefixCode = 0x04;
    remainingUrl = url.substring(8);
  } else if (url.startsWith("http://")) {
    prefixCode = 0x03;
    remainingUrl = url.substring(7);
  }

  size_t remainingLength = remainingUrl.length();
  size_t payloadLength = remainingLength + 1;
  if (payloadLength > 120) {
    return false;
  }

  record[0] = 0xD1;
  record[1] = 0x01;
  record[2] = static_cast<uint8_t>(payloadLength);
  record[3] = 0x55;
  record[4] = prefixCode;
  memcpy(record + 5, remainingUrl.c_str(), remainingLength);

  *recordLength = remainingLength + 5;
  return true;
}

bool buildTextRecord(const String &text, uint8_t *record, size_t *recordLength) {
  const char *languageCode = "en";
  size_t languageLength = 2;
  size_t textLength = text.length();
  size_t payloadLength = 1 + languageLength + textLength;

  if (payloadLength > 120) {
    return false;
  }

  record[0] = 0xD1;
  record[1] = 0x01;
  record[2] = static_cast<uint8_t>(payloadLength);
  record[3] = 0x54;
  record[4] = static_cast<uint8_t>(languageLength);
  memcpy(record + 5, languageCode, languageLength);
  memcpy(record + 5 + languageLength, text.c_str(), textLength);

  *recordLength = 5 + languageLength + textLength;
  return true;
}

void sendStatus(const char *status, const String &message, const String &payload) {
  StaticJsonDocument<256> response;
  response["status"] = status;
  response["message"] = message;
  if (payload.length() > 0) {
    response["payload"] = payload;
  }

  serializeJson(response, Serial);
  Serial.println();
}
