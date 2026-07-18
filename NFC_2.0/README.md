# NFC Digital Receipt Point-of-Sale System

This project combines a Python desktop POS application with an ESP32 + PN532 NFC writer. The cashier creates a receipt in the POS app, stores it locally as text/JSON/PDF/PNG, and sends a compact receipt reference to the ESP32 over USB serial for NFC writing.

## Project Structure

```text
NFC/
|
+-- python_pos/
|   +-- main.py
|   +-- catalog_manager.py
|   +-- camera_scanner.py
|   +-- receipt_generator.py
|   +-- serial_manager.py
|   +-- storage_manager.py
|   +-- product_catalog.json
|   +-- requirements.txt
|   +-- receipts/
|
+-- esp32_nfc/
|   +-- esp32_nfc.ino
|
+-- README.md
```

## Features

- Desktop POS built with Tkinter
- Multiple-product receipt entry
- Barcode / PLU scanning from a local product catalog
- Camera barcode scanning with a webcam
- Continuous camera scanning until you press `Q` or `Esc`
- Automatic date, time, and receipt number
- GST calculation with a default 9% rate
- Receipt preview inside the app
- Receipt export to `.txt`, `.json`, `.pdf`, and `.png`
- Receipt printing through the default system printer
- USB serial communication with an ESP32
- NFC writing with a PN532 module using a compact NDEF payload

## Python POS Setup

### 1. Install Python

Use Python 3.10 or newer.

Check your version:

```powershell
python --version
```

### 2. Create a virtual environment

```powershell
cd C:\Users\kumar\Desktop\NFC
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Python libraries

```powershell
pip install -r python_pos\requirements.txt
```

Installed libraries:

- `reportlab` for PDF receipt generation
- `Pillow` for PNG receipt generation
- `pyserial` for ESP32 communication
- `opencv-python` for webcam access
- `pyzbar` for barcode decoding

## Running the POS Application

From the project root:

```powershell
python python_pos\main.py
```

## How to Use the POS Application

1. Enter the shop name.
2. Scan a barcode / PLU with a USB scanner, type the code manually and click `Scan Barcode`, or click `Scan With Camera`.
3. If needed, edit [python_pos/product_catalog.json](./python_pos/product_catalog.json) and click `Reload Catalog`.
4. You can also add products manually by entering the product name, unit price, and quantity, then clicking `Add Product`.
5. Repeat for additional products.
6. Adjust GST if needed. The default is `9`.
7. Click `Generate Receipt` to preview the receipt.
8. Click `Save Receipt` to save the `.txt` and `.json` versions.
9. Click `Export PDF` or `Export PNG` for formatted versions.
10. Click `Print Receipt` to print with the default printer.
11. Connect the ESP32 over USB, then use `Refresh Ports`, `Connect`, and `Send to ESP32`.
12. Leave `Receipt Base URL (optional)` blank for the offline prototype, or enter a real base URL to send `receipt_url` as well.

Generated files are saved in [python_pos/receipts](./python_pos/receipts).

## Receipt File Names

Each generated receipt uses the receipt number:

```text
Receipt_R20260626153045.txt
Receipt_R20260626153045.json
Receipt_R20260626153045.pdf
Receipt_R20260626153045.png
```

## Sample Receipt Output

```text
================================================
                 ABC MINI MART
================================================
Receipt No: R20260626153045
Date: 26/06/2026
Time: 03:30:45 PM
------------------------------------------------
Product              Price   Qty           Total
------------------------------------------------
Milk                 $3.50     2           $7.00
Bread                $2.80     1           $2.80
Eggs                 $5.90     1           $5.90
------------------------------------------------
Subtotal:                             $15.70
GST (9%):                              $1.41
Final Total:                          $17.11
================================================
             Thank you for shopping!
================================================
```

## Local Receipt Storage

The POS app stores every completed receipt as JSON. Example structure:

```json
{
  "receipt_id": "R20260626153045",
  "shop_name": "ABC Mini Mart",
  "date": "26/06/2026",
  "time": "03:30:45 PM",
  "products": [
    {
      "name": "Milk",
      "price": 3.5,
      "quantity": 2,
      "total": 7.0
    }
  ],
  "subtotal": 15.7,
  "gst_rate": 9.0,
  "gst_amount": 1.41,
  "final_total": 17.11
}
```

The `StorageManager` also builds a compact `receipt_id` / `receipt_url` payload for future cloud-hosted receipts with services such as Supabase or Firebase.

## Barcode and PLU Catalog

The POS app includes a local catalog file at [python_pos/product_catalog.json](./python_pos/product_catalog.json).

You can scan a barcode with a USB barcode scanner, type a barcode / PLU manually into the `Barcode / PLU Scan` field, or click `Scan With Camera` to use the webcam. The app will identify the item, show the match, and add it to the receipt.

When camera scanning is open, it stays active so you can scan multiple products in one session. Press `Q` or `Esc` to finish.

Sample catalog entries:

```json
[
  { "barcode": "200001", "name": "Orange", "price": 1.2 },
  { "barcode": "100001", "name": "Milk 1L", "price": 3.5 }
]
```

If you edit the catalog while the app is running, click `Reload Catalog` to refresh the lookup list.

## ESP32 + PN532 Setup

### Hardware Needed

- ESP32 development board
- PN532 NFC module
- NFC tags or cards based on NTAG / Mifare Ultralight-style memory
- USB cable
- Jumper wires

### Arduino IDE Libraries

Install these libraries from the Arduino Library Manager:

- `ArduinoJson`
- `Adafruit PN532`

### Recommended PN532 Mode

Set the PN532 board to `I2C` mode.

### Wiring

Use this wiring for a common ESP32 dev board:

- `PN532 VCC` -> `ESP32 3.3V`
- `PN532 GND` -> `ESP32 GND`
- `PN532 SDA` -> `ESP32 GPIO21`
- `PN532 SCL` -> `ESP32 GPIO22`
- `PN532 IRQ` -> `ESP32 GPIO4`
- `PN532 RSTO` -> `ESP32 GPIO5`

Open [esp32_nfc/esp32_nfc.ino](./esp32_nfc/esp32_nfc.ino) in Arduino IDE, choose your ESP32 board, then upload it.

## How Python and ESP32 Communicate

The Python app sends a single-line JSON message over USB serial using `pyserial`.

Example offline prototype payload:

```json
{"receipt_id":"R20260626153045"}
```

Example future cloud payload:

```json
{"receipt_id":"R20260626153045","receipt_url":"https://example.com/receipt/R20260626153045"}
```

The ESP32:

1. Reads the JSON line from serial
2. Validates that `receipt_id` or `receipt_url` exists
3. Waits for an NFC tag
4. Writes an NDEF URI or text record to the tag
5. Returns a JSON success or error response back to Python

Example ESP32 response:

```json
{"status":"ok","message":"NFC write successful.","payload":"R20260626153045"}
```

## Testing Serial Communication

1. Plug the ESP32 into the computer.
2. Open the POS application.
3. Click `Refresh Ports`.
4. Select the ESP32 serial port.
5. Click `Connect`.
6. Click `Generate Receipt`.
7. Click `Send to ESP32`.
8. Watch the serial status message in the app.
9. If you want extra debugging, open Arduino IDE Serial Monitor at `115200` baud.

## Testing NFC Writing

1. Make sure the ESP32 sketch is uploaded successfully.
2. Open the POS app and connect to the ESP32.
3. Generate a receipt and click `Send to ESP32`.
4. When prompted by the Serial Monitor or app status, tap a writable NFC tag on the PN532.
5. Wait for the success response.
6. Test the tag with an NFC-enabled phone.

Expected behavior:

- If a `receipt_url` is sent, the phone should read a URL record.
- If only a `receipt_id` is sent, the phone should read a text record containing the receipt ID.

## Common Error Solutions

### Python app does not start

- Make sure you installed the libraries with `pip install -r python_pos\requirements.txt`
- Check that you are using Python 3.10 or newer

### PDF export fails

- Confirm `reportlab` is installed in the active environment

### PNG export fails

- Confirm `Pillow` is installed in the active environment

### Camera scan does not start

- Run `pip install -r python_pos\requirements.txt` to install `opencv-python` and `pyzbar`
- Close other apps that may already be using the webcam
- If the camera window opens but no code is detected, move the barcode closer and improve lighting

### No serial ports appear

- Reconnect the ESP32 USB cable
- Install the correct USB-to-serial driver for your ESP32 board
- Click `Refresh Ports` again

### Serial connection fails

- Make sure no other app has opened the same COM port
- Confirm the ESP32 is powered and the correct port is selected

### PN532 not detected

- Verify the module is set to `I2C` mode
- Double-check `SDA`, `SCL`, `IRQ`, and `RSTO` wiring
- Confirm the board is powered from `3.3V`

### NFC tag write fails

- Use a writable tag with enough space for an NDEF message
- Hold the tag steadily on the PN532 while writing
- Try a shorter payload if you are storing a long URL

## Key Python Classes

- `Product` represents a single line item
- `Receipt` stores the full receipt data
- `ProductCatalogManager` loads barcode and PLU product definitions
- `CameraScanner` opens the webcam and decodes barcodes
- `POSApplication` builds the desktop app
- `ReceiptGenerator` creates previews and exports
- `SerialManager` handles USB serial communication
- `StorageManager` stores JSON data and receipt references

## Notes for Future Expansion

- Replace the placeholder receipt base URL with a real hosted endpoint
- Upload receipt JSON/PDF/PNG to Supabase or Firebase
- Add a search screen for old receipts
- Add a mobile app that reads a `receipt_id` and loads the full receipt
