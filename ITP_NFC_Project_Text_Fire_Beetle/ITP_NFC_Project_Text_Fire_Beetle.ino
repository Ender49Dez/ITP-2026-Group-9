#include <SPI.h>
#include <PN532_SPI.h>
#include <PN532.h>
#include <emulatetag.h>
// Other pins for reference
//11 MOSI
//12 SCK
//13 MISO
PN532_SPI pn532spi(SPI, 5); // Standard CS pin
PN532 pn532(pn532spi);
EmulateTag emulateTag(pn532spi);
uint8_t ndefBuf[10000];
void setup() {
  Serial.setRxBufferSize(10240); // Prevent ESP32 hardware from dropping long JSON strings
  Serial.begin(115200);
  Serial.println("---- NFC Tag Emulation with Short JSON ----");
  pn532.begin();
  uint32_t versiondata = pn532.getFirmwareVersion();
  if (!versiondata) {
    Serial.println("Error: Could not detect PN532. Check wiring.");
    while (1) delay(10);
  }
  Serial.println("PN532 detected!");
  emulateTag.init();
  
  // Minified custom JSON to bypass Serial limitations!
  updateNdef("{\"receipt_id\":\"R20260626144155\",\"shop_name\":\"Fair Price Mart\",\"date\":\"26/06/2026\",\"time\":\"02:41:55 PM\",\"products\":[{\"name\":\"Milk\",\"price\":3.5,\"quantity\":2,\"total\":7.0},{\"name\":\"Bread\",\"price\":2.8,\"quantity\":1,\"total\":2.8}],\"subtotal\":9.8,\"gst_rate\":9.0,\"gst_amount\":0.88,\"final_total\":10.68}");
}
void loop() {
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    if (input.length() > 0 && input.startsWith("{")) {
      updateNdef(input.c_str());
    }
  }
  emulateTag.emulate(500); 
}
uint8_t dynamicUid[3] = {0x12, 0x34, 0x56};

void updateNdef(const char* text) {
  int textLength = strlen(text);
  
  // Payload length for Text Record includes 1 byte Status + 2 bytes Language ("en")
  int payloadLength = textLength + 3; 
  int offset = 0;
  // NDEF Message Header for Text Record (TNF=1)
  if (payloadLength <= 255) {
      ndefBuf[offset++] = 0xD1; // MB=1, ME=1, SR=1, TNF=1
      ndefBuf[offset++] = 0x01; // Type Length
      ndefBuf[offset++] = payloadLength;
  } else {
      ndefBuf[offset++] = 0xC1; // MB=1, ME=1, SR=0, TNF=1
      ndefBuf[offset++] = 0x01; // Type Length
      ndefBuf[offset++] = (payloadLength >> 24) & 0xFF; 
      ndefBuf[offset++] = (payloadLength >> 16) & 0xFF; 
      ndefBuf[offset++] = (payloadLength >> 8) & 0xFF;  
      ndefBuf[offset++] = payloadLength & 0xFF;         
  }
  // Type: "T" (Text)
  ndefBuf[offset++] = 0x54; 
  
  // Status byte (UTF-8, language code length 2)
  ndefBuf[offset++] = 0x02; 
  
  // Language code "en"
  ndefBuf[offset++] = 'e';
  ndefBuf[offset++] = 'n';
  
  // Payload (JSON Data)
  memcpy(&ndefBuf[offset], text, textLength);
  offset += textLength;
  emulateTag.setNdefFile(ndefBuf, offset);
  
  // Change the UID slightly on every update so Android doesn't use its cached NDEF
  dynamicUid[0]++;
  emulateTag.setUid(dynamicUid);
  
  Serial.println("{\"status\":\"success\",\"message\":\"Updated NFC tag! Try scanning now!\"}");
}