
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from catalog_manager import ProductCatalogManager
from camera_scanner import CameraScanResult, CameraScanner, CameraScannerError
from receipt_generator import Product, Receipt, ReceiptGenerator, format_currency
from serial_manager import SerialManager
from storage_manager import StorageManager


class POSApplication(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title("NFC Digital Receipt POS")
        self.geometry("1400x860")
        self.minsize(1200, 760)
        self.configure(bg="#eef1f5")

        base_dir = Path(__file__).resolve().parent
        receipts_dir = base_dir / "receipts"

        self.receipt_generator = ReceiptGenerator(receipts_dir)
        self.storage_manager = StorageManager(receipts_dir)
        self.serial_manager = SerialManager()
        self.catalog_manager = ProductCatalogManager(base_dir / "product_catalog.json")
        self.camera_scanner = CameraScanner()

        self.products: list[Product] = []
        self.current_receipt: Receipt | None = None
        self.receipt_dirty = True

        self.shop_name_var = tk.StringVar(value="ABC Mini Mart")
        self.barcode_var = tk.StringVar()
        self.product_name_var = tk.StringVar()
        self.product_price_var = tk.StringVar()
        self.quantity_var = tk.StringVar(value="1")
        self.gst_rate_var = tk.StringVar(value="9")
        self.receipt_id_var = tk.StringVar()
        self.date_var = tk.StringVar()
        self.time_var = tk.StringVar()
        self.subtotal_var = tk.StringVar(value=format_currency(0))
        self.gst_amount_var = tk.StringVar(value=format_currency(0))
        self.final_total_var = tk.StringVar(value=format_currency(0))
        self.serial_port_var = tk.StringVar()
        self.serial_status_var = tk.StringVar(value="No ESP32 connected.")
        self.receipt_base_url_var = tk.StringVar()
        self.scan_result_var = tk.StringVar()
        self.app_status_var = tk.StringVar(value="Ready.")

        self._create_styles()
        self._build_layout()
        self._wire_events()
        self._set_catalog_status()
        self.refresh_serial_ports(select_first=True)
        self.update_totals()
        self._update_clock()

    def _create_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("TFrame", background="#eef1f5")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Header.TLabel", background="#ffffff", font=("Segoe UI Semibold", 18))
        style.configure("Section.TLabel", background="#ffffff", font=("Segoe UI Semibold", 11))
        style.configure("Meta.TLabel", background="#ffffff", foreground="#475569", font=("Segoe UI", 10))
        style.configure("Value.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI", 11))
        style.configure("Strong.TLabel", background="#ffffff", foreground="#0f172a", font=("Segoe UI Semibold", 11))
        style.configure("Summary.TLabel", background="#ffffff", foreground="#0f172a", font=("Segoe UI Semibold", 12))
        style.configure("TButton", font=("Segoe UI", 10), padding=(10, 7))
        style.configure("Accent.TButton", font=("Segoe UI Semibold", 10), padding=(12, 8))
        style.configure(
            "Treeview",
            background="#ffffff",
            fieldbackground="#ffffff",
            rowheight=30,
            font=("Segoe UI", 10),
        )
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 10))

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        container = ttk.Frame(self, padding=16)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=3)
        container.columnconfigure(1, weight=2)
        container.rowconfigure(0, weight=1)

        left_panel = ttk.Frame(container, style="Card.TFrame", padding=18)
        right_panel = ttk.Frame(container, style="Card.TFrame", padding=18)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right_panel.grid(row=0, column=1, sticky="nsew")

        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(3, weight=1)
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)

        self._build_header_section(left_panel)
        self._build_entry_section(left_panel)
        self._build_table_section(left_panel)
        self._build_summary_section(left_panel)
        self._build_action_section(left_panel)
        self._build_status_section(left_panel)

        self._build_serial_section(right_panel)
        self._build_preview_section(right_panel)

    def _build_header_section(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent, style="Card.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        header.columnconfigure(3, weight=1)

        ttk.Label(header, text="NFC Digital Receipt POS", style="Header.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 12)
        )

        ttk.Label(header, text="Shop Name", style="Section.TLabel").grid(row=1, column=0, sticky="w", pady=(0, 4))
        self.shop_name_entry = ttk.Entry(header, textvariable=self.shop_name_var, font=("Segoe UI", 11))
        self.shop_name_entry.grid(row=2, column=0, columnspan=2, sticky="ew", padx=(0, 12), pady=(0, 12))

        ttk.Label(header, text="Receipt Number", style="Section.TLabel").grid(row=1, column=2, sticky="w", pady=(0, 4))
        ttk.Label(header, textvariable=self.receipt_id_var, style="Value.TLabel").grid(row=2, column=2, sticky="w")

        ttk.Label(header, text="Date", style="Section.TLabel").grid(row=3, column=0, sticky="w", pady=(0, 4))
        ttk.Label(header, textvariable=self.date_var, style="Meta.TLabel").grid(row=4, column=0, sticky="w", pady=(0, 12))

        ttk.Label(header, text="Time", style="Section.TLabel").grid(row=3, column=1, sticky="w", pady=(0, 4))
        ttk.Label(header, textvariable=self.time_var, style="Meta.TLabel").grid(row=4, column=1, sticky="w", pady=(0, 12))

    def _build_entry_section(self, parent: ttk.Frame) -> None:
        section = ttk.Frame(parent, style="Card.TFrame")
        section.grid(row=1, column=0, sticky="ew", pady=(8, 14))
        for column in range(6):
            section.columnconfigure(column, weight=1)

        ttk.Label(section, text="Product Entry", style="Section.TLabel").grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 8))

        ttk.Label(section, text="Barcode / PLU Scan", style="Meta.TLabel").grid(row=1, column=0, columnspan=3, sticky="w")
        self.barcode_entry = ttk.Entry(section, textvariable=self.barcode_var, font=("Segoe UI", 10))
        self.barcode_entry.grid(row=2, column=0, columnspan=3, sticky="ew", padx=(0, 10), pady=(4, 0))
        ttk.Button(section, text="Scan Barcode", style="Accent.TButton", command=self.scan_barcode).grid(
            row=2, column=3, sticky="ew", padx=(0, 10), pady=(4, 0)
        )
        ttk.Button(section, text="Scan With Camera", command=self.scan_with_camera).grid(
            row=2, column=4, sticky="ew", pady=(4, 0)
        )
        ttk.Button(section, text="Reload Catalog", command=self.reload_catalog).grid(
            row=2, column=5, sticky="ew", padx=(10, 0), pady=(4, 0)
        )

        ttk.Label(section, textvariable=self.scan_result_var, style="Meta.TLabel", wraplength=780).grid(
            row=3, column=0, columnspan=6, sticky="w", pady=(8, 12)
        )

        ttk.Separator(section).grid(row=4, column=0, columnspan=6, sticky="ew", pady=(0, 12))

        ttk.Label(section, text="Manual Product Entry", style="Section.TLabel").grid(
            row=5, column=0, columnspan=6, sticky="w", pady=(0, 8)
        )

        ttk.Label(section, text="Product Name", style="Meta.TLabel").grid(row=6, column=0, columnspan=2, sticky="w")
        ttk.Label(section, text="Unit Price (SGD)", style="Meta.TLabel").grid(row=6, column=2, sticky="w")
        ttk.Label(section, text="Quantity", style="Meta.TLabel").grid(row=6, column=3, sticky="w")

        self.product_name_entry = ttk.Entry(section, textvariable=self.product_name_var, font=("Segoe UI", 10))
        self.product_price_entry = ttk.Entry(section, textvariable=self.product_price_var, font=("Segoe UI", 10))
        self.quantity_entry = ttk.Entry(section, textvariable=self.quantity_var, font=("Segoe UI", 10))

        self.product_name_entry.grid(row=7, column=0, columnspan=2, sticky="ew", padx=(0, 10), pady=(4, 0))
        self.product_price_entry.grid(row=7, column=2, sticky="ew", padx=(0, 10), pady=(4, 0))
        self.quantity_entry.grid(row=7, column=3, sticky="ew", padx=(0, 10), pady=(4, 0))

        ttk.Button(section, text="Add Product", style="Accent.TButton", command=self.add_product).grid(
            row=7, column=4, sticky="ew", padx=(0, 10), pady=(4, 0)
        )
        ttk.Button(section, text="Clear Inputs", command=self.clear_product_inputs).grid(
            row=7, column=5, sticky="ew", pady=(4, 0)
        )

    def _build_table_section(self, parent: ttk.Frame) -> None:
        section = ttk.Frame(parent, style="Card.TFrame")
        section.grid(row=3, column=0, sticky="nsew")
        section.columnconfigure(0, weight=1)
        section.rowconfigure(1, weight=1)

        table_header = ttk.Frame(section, style="Card.TFrame")
        table_header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        table_header.columnconfigure(0, weight=1)

        ttk.Label(table_header, text="Product Table", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(table_header, text="Remove Selected", command=self.remove_selected_product).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(table_header, text="Clear All Products", command=self.clear_products).grid(row=0, column=2, padx=(8, 0))

        table_frame = ttk.Frame(section, style="Card.TFrame")
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = ("name", "price", "quantity", "total")
        self.product_tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        self.product_tree.heading("name", text="Product Name")
        self.product_tree.heading("price", text="Unit Price")
        self.product_tree.heading("quantity", text="Quantity")
        self.product_tree.heading("total", text="Total Price")
        self.product_tree.column("name", width=260, anchor="w")
        self.product_tree.column("price", width=120, anchor="center")
        self.product_tree.column("quantity", width=100, anchor="center")
        self.product_tree.column("total", width=120, anchor="center")
        self.product_tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.product_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.product_tree.configure(yscrollcommand=scrollbar.set)

    def _build_summary_section(self, parent: ttk.Frame) -> None:
        section = ttk.Frame(parent, style="Card.TFrame")
        section.grid(row=4, column=0, sticky="ew", pady=(14, 10))
        for column in range(4):
            section.columnconfigure(column, weight=1)

        ttk.Label(section, text="GST Rate (%)", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.gst_rate_entry = ttk.Entry(section, textvariable=self.gst_rate_var, font=("Segoe UI", 10))
        self.gst_rate_entry.grid(row=1, column=0, sticky="ew", padx=(0, 12), pady=(4, 0))

        ttk.Label(section, text="Subtotal", style="Section.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(section, textvariable=self.subtotal_var, style="Summary.TLabel").grid(row=1, column=1, sticky="w", pady=(4, 0))

        ttk.Label(section, text="GST Amount", style="Section.TLabel").grid(row=0, column=2, sticky="w")
        ttk.Label(section, textvariable=self.gst_amount_var, style="Summary.TLabel").grid(row=1, column=2, sticky="w", pady=(4, 0))

        ttk.Label(section, text="Final Total", style="Section.TLabel").grid(row=0, column=3, sticky="w")
        ttk.Label(section, textvariable=self.final_total_var, style="Summary.TLabel").grid(row=1, column=3, sticky="w", pady=(4, 0))

    def _build_action_section(self, parent: ttk.Frame) -> None:
        section = ttk.Frame(parent, style="Card.TFrame")
        section.grid(row=5, column=0, sticky="ew", pady=(0, 6))
        for column in range(5):
            section.columnconfigure(column, weight=1)

        ttk.Button(section, text="Generate Receipt", style="Accent.TButton", command=self.generate_receipt_preview).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(section, text="Save Receipt", command=self.save_receipt).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(section, text="Export PDF", command=self.export_pdf).grid(row=0, column=2, sticky="ew", padx=(0, 8))
        ttk.Button(section, text="Export PNG", command=self.export_png).grid(row=0, column=3, sticky="ew", padx=(0, 8))
        ttk.Button(section, text="Print Receipt", command=self.print_receipt).grid(row=0, column=4, sticky="ew")

    def _build_status_section(self, parent: ttk.Frame) -> None:
        ttk.Separator(parent).grid(row=6, column=0, sticky="ew", pady=(8, 8))
        ttk.Label(parent, textvariable=self.app_status_var, style="Meta.TLabel").grid(row=7, column=0, sticky="w")

    def _build_serial_section(self, parent: ttk.Frame) -> None:
        section = ttk.Frame(parent, style="Card.TFrame")
        section.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        for column in range(3):
            section.columnconfigure(column, weight=1)

        ttk.Label(section, text="ESP32 Serial Connection", style="Header.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 12)
        )

        ttk.Label(section, text="Serial Port", style="Section.TLabel").grid(row=1, column=0, sticky="w")
        self.port_combobox = ttk.Combobox(section, textvariable=self.serial_port_var, state="readonly", font=("Segoe UI", 10))
        self.port_combobox.grid(row=2, column=0, sticky="ew", padx=(0, 10), pady=(4, 8))
        ttk.Button(section, text="Refresh Ports", command=lambda: self.refresh_serial_ports(select_first=False)).grid(
            row=2, column=1, sticky="ew", padx=(0, 10), pady=(4, 8)
        )
        self.connect_button = ttk.Button(section, text="Connect", command=self.toggle_serial_connection)
        self.connect_button.grid(row=2, column=2, sticky="ew", pady=(4, 8))

        ttk.Label(section, text="Receipt Base URL (optional)", style="Section.TLabel").grid(row=3, column=0, columnspan=3, sticky="w")
        ttk.Entry(section, textvariable=self.receipt_base_url_var, font=("Segoe UI", 10)).grid(
            row=4, column=0, columnspan=3, sticky="ew", pady=(4, 8)
        )

        ttk.Button(section, text="Send to ESP32", style="Accent.TButton", command=self.send_to_esp32).grid(
            row=5, column=0, columnspan=3, sticky="ew", pady=(4, 8)
        )
        ttk.Label(section, textvariable=self.serial_status_var, style="Meta.TLabel", wraplength=420).grid(
            row=6, column=0, columnspan=3, sticky="w"
        )

    def _build_preview_section(self, parent: ttk.Frame) -> None:
        section = ttk.Frame(parent, style="Card.TFrame")
        section.grid(row=1, column=0, sticky="nsew")
        section.columnconfigure(0, weight=1)
        section.rowconfigure(1, weight=1)

        ttk.Label(section, text="Receipt Preview", style="Header.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 12))

        preview_frame = ttk.Frame(section, style="Card.TFrame")
        preview_frame.grid(row=1, column=0, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        self.preview_text = tk.Text(
            preview_frame,
            wrap="none",
            font=("Consolas", 11),
            bg="#f8fafc",
            fg="#111827",
            relief="flat",
            padx=12,
            pady=12,
        )
        self.preview_text.grid(row=0, column=0, sticky="nsew")
        preview_scrollbar = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview_text.yview)
        preview_scrollbar.grid(row=0, column=1, sticky="ns")
        self.preview_text.configure(yscrollcommand=preview_scrollbar.set)
        self._set_preview_text("Generate a receipt to preview it here.")

    def _wire_events(self) -> None:
        self.shop_name_var.trace_add("write", lambda *_: self._mark_receipt_dirty())
        self.gst_rate_var.trace_add("write", lambda *_: self._handle_gst_change())
        self.bind("<Delete>", lambda _event: self.remove_selected_product())
        self.barcode_entry.bind("<Return>", lambda _event: self.scan_barcode())
        self.product_name_entry.bind("<Return>", lambda _event: self.add_product())
        self.product_price_entry.bind("<Return>", lambda _event: self.add_product())
        self.quantity_entry.bind("<Return>", lambda _event: self.add_product())

    def _update_clock(self) -> None:
        from datetime import datetime

        now = datetime.now()
        self.date_var.set(now.strftime("%d/%m/%Y"))
        self.time_var.set(now.strftime("%I:%M:%S %p"))
        if self.current_receipt is None or self.receipt_dirty:
            self.receipt_id_var.set(f"R{now.strftime('%Y%m%d%H%M%S')}")
        self.after(1000, self._update_clock)

    def _handle_gst_change(self) -> None:
        self._mark_receipt_dirty()
        self.update_totals()

    def _mark_receipt_dirty(self) -> None:
        self.current_receipt = None
        self.receipt_dirty = True

    def clear_product_inputs(self) -> None:
        self.product_name_var.set("")
        self.product_price_var.set("")
        self.quantity_var.set("1")
        self.product_name_entry.focus_set()

    def reload_catalog(self) -> None:
        self.catalog_manager.reload()
        self._set_catalog_status()
        if self.catalog_manager.load_error:
            self.app_status_var.set(self.catalog_manager.load_error)
            messagebox.showerror("Product Catalog", self.catalog_manager.load_error)
            return

        self.app_status_var.set(f"Reloaded product catalog with {self.catalog_manager.item_count} item(s).")
        self.barcode_entry.focus_set()

    def scan_barcode(self) -> None:
        barcode = self.barcode_var.get().strip()
        if not barcode:
            messagebox.showerror("Missing Barcode", "Scan or enter a barcode or PLU before continuing.")
            return

        self._process_catalog_barcode(barcode, source_label="barcode")

    def scan_with_camera(self) -> None:
        self.app_status_var.set("Opening camera scanner. Press Q or Esc in the camera window to finish.")
        self.update_idletasks()
        scanned_product_count = 0

        def handle_camera_detection(scan_result: CameraScanResult) -> bool:
            nonlocal scanned_product_count

            self.barcode_var.set(scan_result.value)
            self._set_catalog_status(
                f"Camera detected {scan_result.symbology}: {scan_result.value}. Matching it against the catalog."
            )
            if self._process_catalog_barcode(scan_result.value, source_label="camera scan"):
                scanned_product_count += 1
                self.update_idletasks()
            return True

        try:
            self.camera_scanner.scan_session(on_detect=handle_camera_detection)
        except CameraScannerError as error:
            self.app_status_var.set(str(error))
            messagebox.showerror("Camera Scanner", str(error))
            self._restore_focus_after_camera_scan()
            return

        self._restore_focus_after_camera_scan()
        if scanned_product_count == 0:
            self.app_status_var.set("Camera scan finished. No products were added.")
            self._set_catalog_status()
            return

        self.app_status_var.set(f"Camera scan finished. Added or updated {scanned_product_count} item(s).")

    def _process_catalog_barcode(self, barcode: str, source_label: str) -> bool:

        if self.catalog_manager.load_error:
            messagebox.showerror("Product Catalog", self.catalog_manager.load_error)
            self.app_status_var.set(self.catalog_manager.load_error)
            return False

        try:
            quantity = self._validate_positive_integer(self.quantity_var.get(), "Quantity")
        except ValueError as error:
            messagebox.showerror("Invalid Quantity", str(error))
            return False

        catalog_item = self.catalog_manager.lookup(barcode)
        if catalog_item is None:
            self._set_catalog_status(
                f"Barcode {barcode} was not found in {self.catalog_manager.catalog_path.name}. "
                "Add it to the catalog file, then click Reload Catalog."
            )
            self.app_status_var.set(f"Unknown barcode: {barcode}")
            self.barcode_entry.focus_set()
            self.barcode_entry.selection_range(0, tk.END)
            return False

        product = Product(name=catalog_item.name, price=catalog_item.price, quantity=quantity)
        merged_existing = self._add_product_to_cart(product, merge_existing=True)
        self._refresh_product_table()
        self.update_totals()
        self._mark_receipt_dirty()

        self.product_name_var.set(catalog_item.name)
        self.product_price_var.set(f"{catalog_item.price:.2f}")
        self.barcode_var.set("")
        self.quantity_var.set("1")

        self._set_catalog_status(
            f"Identified {barcode} as {catalog_item.name} at {format_currency(catalog_item.price)}."
        )
        if merged_existing:
            self.app_status_var.set(f"Updated quantity for {catalog_item.name} from {source_label} {barcode}.")
        else:
            self.app_status_var.set(f"Added {catalog_item.name} from {source_label} {barcode}.")

        self.barcode_entry.focus_set()
        return True

    def add_product(self) -> None:
        try:
            price = self._validate_positive_decimal(self.product_price_var.get(), "Product price")
            quantity = self._validate_positive_integer(self.quantity_var.get(), "Quantity")
            product = Product(
                name=self.product_name_var.get(),
                price=price,
                quantity=quantity,
            )
        except ValueError as error:
            messagebox.showerror("Invalid Product", str(error))
            return

        self._add_product_to_cart(product, merge_existing=False)
        self._refresh_product_table()
        self.update_totals()
        self._mark_receipt_dirty()
        self.clear_product_inputs()
        self.app_status_var.set(f"Added product: {product.name}")

    def remove_selected_product(self) -> None:
        selection = self.product_tree.selection()
        if not selection:
            messagebox.showerror("No Selection", "Select a product row to remove.")
            return

        row_index = int(selection[0])
        removed_product = self.products.pop(row_index)
        self._refresh_product_table()
        self.update_totals()
        self._mark_receipt_dirty()
        self.app_status_var.set(f"Removed product: {removed_product.name}")

    def clear_products(self) -> None:
        self.products.clear()
        self._refresh_product_table()
        self.update_totals()
        self._mark_receipt_dirty()
        self._set_preview_text("Generate a receipt to preview it here.")
        self.app_status_var.set("All products were cleared.")

    def _refresh_product_table(self) -> None:
        for item in self.product_tree.get_children():
            self.product_tree.delete(item)

        for index, product in enumerate(self.products):
            self.product_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    product.name,
                    format_currency(product.price),
                    product.quantity,
                    format_currency(product.total),
                ),
            )

    def _add_product_to_cart(self, product: Product, merge_existing: bool) -> bool:
        if merge_existing:
            for existing_product in self.products:
                if (
                    existing_product.name.casefold() == product.name.casefold()
                    and existing_product.price == product.price
                ):
                    existing_product.quantity += product.quantity
                    return True

        self.products.append(product)
        return False

    def update_totals(self) -> None:
        subtotal = sum((product.total for product in self.products), Decimal("0.00"))
        self.subtotal_var.set(format_currency(subtotal))

        gst_rate = self._get_gst_rate(show_message=False)
        if gst_rate is None:
            self.gst_amount_var.set("Invalid GST")
            self.final_total_var.set("Invalid GST")
            return

        gst_amount = subtotal * gst_rate / Decimal("100")
        final_total = subtotal + gst_amount
        self.gst_amount_var.set(format_currency(gst_amount))
        self.final_total_var.set(format_currency(final_total))

    def generate_receipt_preview(self) -> None:
        receipt = self._ensure_receipt()
        if receipt is None:
            return
        self.app_status_var.set(f"Receipt {receipt.receipt_id} generated for preview.")

    def save_receipt(self) -> None:
        receipt = self._ensure_receipt()
        if receipt is None:
            return

        try:
            text_path = self.receipt_generator.save_text(receipt)
            json_path = self.storage_manager.save_receipt_json(receipt)
        except OSError as error:
            messagebox.showerror("Save Failed", f"Unable to save the receipt files.\n\n{error}")
            return

        self.app_status_var.set(f"Saved receipt files to {text_path.parent}")
        
        if self.serial_manager.is_connected():
            import json
            payload = self.storage_manager.build_receipt_serial_payload(
                receipt,
                base_url=self.receipt_base_url_var.get().strip(),
            )
            payload_str = json.dumps(payload, separators=(",", ":"))
            payload_bytes = len(payload_str.encode("utf-8"))
            
            success, message = self.serial_manager.send_receipt_reference(payload)
            self.serial_status_var.set(message)
            
            if success:
                messagebox.showinfo("Saved & Sent to ESP32", f"Receipt saved locally!\n\nPayload Size: {payload_bytes} bytes\nNFC Status: {message}")
            else:
                messagebox.showwarning("Saved but Send Failed", f"Receipt saved locally, but failed to send to ESP32:\n\nPayload Size: {payload_bytes} bytes\nNFC Status: {message}")
        else:
            messagebox.showinfo("Receipt Saved", f"Receipt saved locally!\n\n(ESP32 is not connected, so it was not sent via NFC.)")

    def export_pdf(self) -> None:
        receipt = self._ensure_receipt()
        if receipt is None:
            return

        try:
            pdf_path = self.receipt_generator.generate_pdf(receipt)
        except (OSError, RuntimeError) as error:
            messagebox.showerror("PDF Export Failed", str(error))
            return

        self.app_status_var.set(f"Exported PDF receipt: {pdf_path.name}")
        messagebox.showinfo("PDF Exported", f"PDF receipt created at:\n{pdf_path}")

    def export_png(self) -> None:
        receipt = self._ensure_receipt()
        if receipt is None:
            return

        try:
            png_path = self.receipt_generator.generate_png(receipt)
        except (OSError, RuntimeError) as error:
            messagebox.showerror("PNG Export Failed", str(error))
            return

        self.app_status_var.set(f"Exported PNG receipt: {png_path.name}")
        messagebox.showinfo("PNG Exported", f"PNG receipt created at:\n{png_path}")

    def print_receipt(self) -> None:
        receipt = self._ensure_receipt()
        if receipt is None:
            return

        try:
            printed_path = self.receipt_generator.print_receipt(receipt)
        except (OSError, RuntimeError, FileNotFoundError) as error:
            messagebox.showerror("Print Failed", str(error))
            return

        self.app_status_var.set(f"Sent receipt {receipt.receipt_id} to the default printer.")
        messagebox.showinfo("Print Started", f"The receipt was sent to the default printer.\n\nSource file:\n{printed_path}")

    def refresh_serial_ports(self, select_first: bool) -> None:
        ports = self.serial_manager.list_available_ports()
        self.port_combobox["values"] = ports

        if ports and (select_first or self.serial_port_var.get() not in ports):
            self.serial_port_var.set(ports[0])
        elif not ports:
            self.serial_port_var.set("")

        if ports:
            self.serial_status_var.set(f"Found {len(ports)} serial port(s).")
        else:
            self.serial_status_var.set("No serial ports detected. Connect the ESP32 and refresh.")

    def toggle_serial_connection(self) -> None:
        if self.serial_manager.is_connected():
            success, message = self.serial_manager.disconnect()
            self.connect_button.configure(text="Connect")
        else:
            success, message = self.serial_manager.connect(self.serial_port_var.get())
            if success:
                self.connect_button.configure(text="Disconnect")

        self.serial_status_var.set(message)
        self.app_status_var.set(message)
        if not success:
            messagebox.showerror("Serial Connection", message)

    def send_to_esp32(self) -> None:
        receipt = self._ensure_receipt()
        if receipt is None:
            return

        try:
            json_path = self.storage_manager.save_receipt_json(receipt)
        except OSError as error:
            messagebox.showerror("JSON Save Failed", f"Unable to save the receipt JSON file.\n\n{error}")
            return

        import json
        payload = self.storage_manager.build_receipt_serial_payload(
            receipt,
            base_url=self.receipt_base_url_var.get().strip(),
        )
        payload_str = json.dumps(payload, separators=(",", ":"))
        payload_bytes = len(payload_str.encode("utf-8"))

        success, message = self.serial_manager.send_receipt_reference(payload)
        self.serial_status_var.set(message)
        self.app_status_var.set(f"{message} JSON file: {json_path.name}")
        if success:
            messagebox.showinfo("Serial Transfer", f"{message}\n\nPayload Size: {payload_bytes} bytes\nSent JSON file:\n{json_path}")
        else:
            messagebox.showerror("Serial Transfer", f"{message}\n\nPayload Size: {payload_bytes} bytes\nJSON file saved at:\n{json_path}")

    def _ensure_receipt(self) -> Receipt | None:
        if not self.products:
            messagebox.showerror("No Products", "Add at least one product before generating a receipt.")
            return None

        shop_name = self.shop_name_var.get().strip()
        if not shop_name:
            messagebox.showerror("Missing Shop Name", "Enter the shop name before generating a receipt.")
            return None

        gst_rate = self._get_gst_rate(show_message=True)
        if gst_rate is None:
            return None

        if self.current_receipt is None or self.receipt_dirty:
            try:
                self.current_receipt = self.receipt_generator.create_receipt(shop_name, list(self.products), gst_rate)
            except ValueError as error:
                messagebox.showerror("Receipt Error", str(error))
                return None

            self.receipt_id_var.set(self.current_receipt.receipt_id)
            self._set_preview_text(self.receipt_generator.build_receipt_text(self.current_receipt))
            self.receipt_dirty = False

        return self.current_receipt

    def _validate_positive_decimal(self, raw_value: str, field_name: str) -> Decimal:
        cleaned_value = raw_value.strip()
        if not cleaned_value:
            raise ValueError(f"{field_name} cannot be empty.")

        try:
            value = Decimal(cleaned_value)
        except InvalidOperation as error:
            raise ValueError(f"{field_name} must be a valid number.") from error

        if value <= 0:
            raise ValueError(f"{field_name} must be greater than zero.")
        return value

    def _validate_positive_integer(self, raw_value: str, field_name: str) -> int:
        cleaned_value = raw_value.strip()
        if not cleaned_value:
            raise ValueError(f"{field_name} cannot be empty.")

        try:
            value = int(cleaned_value)
        except ValueError as error:
            raise ValueError(f"{field_name} must be a positive whole number.") from error

        if value <= 0:
            raise ValueError(f"{field_name} must be greater than zero.")
        return value

    def _get_gst_rate(self, show_message: bool) -> Decimal | None:
        cleaned_value = self.gst_rate_var.get().strip()
        if not cleaned_value:
            if show_message:
                messagebox.showerror("Invalid GST", "GST rate cannot be empty.")
            return None

        try:
            gst_rate = Decimal(cleaned_value)
        except InvalidOperation:
            if show_message:
                messagebox.showerror("Invalid GST", "GST rate must be a valid number.")
            return None

        if gst_rate < 0:
            if show_message:
                messagebox.showerror("Invalid GST", "GST rate cannot be negative.")
            return None
        return gst_rate

    def _set_preview_text(self, text: str) -> None:
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert("1.0", text)
        self.preview_text.configure(state="disabled")

    def _restore_focus_after_camera_scan(self) -> None:
        self.lift()
        self.focus_force()
        self.barcode_entry.focus_set()

    def _set_catalog_status(self, message: str | None = None) -> None:
        if message is not None:
            self.scan_result_var.set(message)
            return

        if self.catalog_manager.load_error:
            self.scan_result_var.set(self.catalog_manager.load_error)
            return

        self.scan_result_var.set(
            f"Catalog ready with {self.catalog_manager.item_count} item(s). "
            "Scan a barcode or PLU to identify and add a product."
        )


def main() -> None:
    app = POSApplication()
    app.mainloop()


if __name__ == "__main__":
    main()
