from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import os
import platform
import shutil
import subprocess


MONEY_PLACES = Decimal("0.01")
RECEIPT_WIDTH = 48


def normalize_money(value: Decimal | float | int | str) -> Decimal:
    """Convert any supported value to a two-decimal-place Decimal."""
    return Decimal(str(value)).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def format_currency(value: Decimal | float | int | str) -> str:
    """Format a number as Singapore dollars."""
    return f"${normalize_money(value):.2f}"


def format_percentage(value: Decimal | float | int | str) -> str:
    """Format a percentage without unnecessary trailing zeroes."""
    normalized = normalize_money(value)
    return format(normalized, "f").rstrip("0").rstrip(".") or "0"


def generate_receipt_id(timestamp: datetime | None = None) -> str:
    timestamp = timestamp or datetime.now()
    return f"R{timestamp.strftime('%Y%m%d%H%M%S')}"


@dataclass(slots=True)
class Product:
    name: str
    price: Decimal
    quantity: int

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Product name cannot be empty.")

        self.price = normalize_money(self.price)
        if self.price <= 0:
            raise ValueError("Product price must be greater than zero.")

        self.quantity = int(self.quantity)
        if self.quantity <= 0:
            raise ValueError("Quantity must be a positive whole number.")

    @property
    def total(self) -> Decimal:
        return normalize_money(self.price * self.quantity)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "price": float(self.price),
            "quantity": self.quantity,
            "total": float(self.total),
        }


@dataclass(slots=True)
class Receipt:
    receipt_id: str
    shop_name: str
    date: str
    time: str
    products: list[Product]
    subtotal: Decimal
    gst_rate: Decimal
    gst_amount: Decimal
    final_total: Decimal

    def to_dict(self) -> dict:
        return {
            "receipt_id": self.receipt_id,
            "shop_name": self.shop_name,
            "date": self.date,
            "time": self.time,
            "products": [product.to_dict() for product in self.products],
            "subtotal": float(self.subtotal),
            "gst_rate": float(self.gst_rate),
            "gst_amount": float(self.gst_amount),
            "final_total": float(self.final_total),
        }


class ReceiptGenerator:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_receipt(
        self,
        shop_name: str,
        products: list[Product],
        gst_rate: Decimal | float | int | str,
        timestamp: datetime | None = None,
    ) -> Receipt:
        if not shop_name.strip():
            raise ValueError("Shop name cannot be empty.")
        if not products:
            raise ValueError("At least one product is required to create a receipt.")

        timestamp = timestamp or datetime.now()
        subtotal = normalize_money(sum((product.total for product in products), Decimal("0.00")))
        gst_rate_decimal = normalize_money(gst_rate)
        gst_amount = normalize_money(subtotal * gst_rate_decimal / Decimal("100"))
        final_total = normalize_money(subtotal + gst_amount)

        return Receipt(
            receipt_id=generate_receipt_id(timestamp),
            shop_name=shop_name.strip(),
            date=timestamp.strftime("%d/%m/%Y"),
            time=timestamp.strftime("%I:%M:%S %p"),
            products=products,
            subtotal=subtotal,
            gst_rate=gst_rate_decimal,
            gst_amount=gst_amount,
            final_total=final_total,
        )

    def build_receipt_lines(self, receipt: Receipt) -> list[str]:
        lines = [
            "=" * RECEIPT_WIDTH,
            receipt.shop_name.upper().center(RECEIPT_WIDTH),
            "=" * RECEIPT_WIDTH,
            f"Receipt No: {receipt.receipt_id}",
            f"Date: {receipt.date}",
            f"Time: {receipt.time}",
            "-" * RECEIPT_WIDTH,
            f"{'Product':16}{'Price':>10}{'Qty':>6}{'Total':>16}",
            "-" * RECEIPT_WIDTH,
        ]

        for product in receipt.products:
            product_name = product.name
            if len(product_name) > 16:
                product_name = f"{product_name[:13]}..."

            lines.append(
                f"{product_name:<16}"
                f"{format_currency(product.price):>10}"
                f"{product.quantity:>6}"
                f"{format_currency(product.total):>16}"
            )

        lines.extend(
            [
                "-" * RECEIPT_WIDTH,
                f"{'Subtotal:':<32}{format_currency(receipt.subtotal):>16}",
                f"{f'GST ({format_percentage(receipt.gst_rate)}%):':<32}{format_currency(receipt.gst_amount):>16}",
                f"{'Final Total:':<32}{format_currency(receipt.final_total):>16}",
                "=" * RECEIPT_WIDTH,
                "Thank you for shopping!".center(RECEIPT_WIDTH),
                "=" * RECEIPT_WIDTH,
            ]
        )
        return lines

    def build_receipt_text(self, receipt: Receipt) -> str:
        return "\n".join(self.build_receipt_lines(receipt))

    def save_text(self, receipt: Receipt) -> Path:
        file_path = self._build_output_path(receipt.receipt_id, "txt")
        file_path.write_text(self.build_receipt_text(receipt), encoding="utf-8")
        return file_path

    def generate_pdf(self, receipt: Receipt) -> Path:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
        except ImportError as error:
            raise RuntimeError("ReportLab is required for PDF generation.") from error

        file_path = self._build_output_path(receipt.receipt_id, "pdf")
        pdf = canvas.Canvas(str(file_path), pagesize=A4)
        _, height = A4
        left_margin = 54
        top_margin = height - 60
        line_height = 16

        lines = self.build_receipt_lines(receipt)
        current_y = top_margin
        for index, line in enumerate(lines):
            if current_y < 60:
                pdf.showPage()
                current_y = top_margin

            if index == 1:
                pdf.setFont("Courier-Bold", 12)
            else:
                pdf.setFont("Courier", 10)

            pdf.drawString(left_margin, current_y, line)
            current_y -= line_height

        pdf.setTitle(f"Receipt {receipt.receipt_id}")
        pdf.save()
        return file_path

    def generate_png(self, receipt: Receipt) -> Path:
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError as error:
            raise RuntimeError("Pillow is required for PNG generation.") from error

        lines = self.build_receipt_lines(receipt)
        body_font = self._load_image_font(ImageFont, size=22, bold=False)
        header_font = self._load_image_font(ImageFont, size=24, bold=True)
        image_width = 860
        line_height = 34
        padding_x = 40
        padding_y = 40
        image_height = (len(lines) * line_height) + (padding_y * 2)

        image = Image.new("RGB", (image_width, image_height), "white")
        draw = ImageDraw.Draw(image)

        for index, line in enumerate(lines):
            font = header_font if index == 1 else body_font
            y_position = padding_y + (index * line_height)
            draw.text((padding_x, y_position), line, fill="black", font=font)

        file_path = self._build_output_path(receipt.receipt_id, "png")
        image.save(file_path)
        return file_path

    def print_receipt(self, receipt: Receipt) -> Path:
        """Print the receipt using the system default printer."""
        system_name = platform.system()

        if system_name == "Windows":
            printable_path = self.generate_pdf(receipt)
            os.startfile(str(printable_path), "print")
            return printable_path

        printable_path = self.save_text(receipt)
        if shutil.which("lp"):
            subprocess.run(["lp", str(printable_path)], check=True)
            return printable_path
        if shutil.which("lpr"):
            subprocess.run(["lpr", str(printable_path)], check=True)
            return printable_path

        raise RuntimeError("No supported print command was found on this computer.")

    def _build_output_path(self, receipt_id: str, extension: str) -> Path:
        return self.output_dir / f"Receipt_{receipt_id}.{extension.lstrip('.')}"

    def _load_image_font(self, image_font_module, size: int, bold: bool):
        windows_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        font_candidates = [
            windows_dir / ("consolab.ttf" if bold else "consola.ttf"),
            windows_dir / ("courbd.ttf" if bold else "cour.ttf"),
            Path("/usr/share/fonts/truetype/dejavu") / ("DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf"),
            Path("/Library/Fonts") / ("Courier New Bold.ttf" if bold else "Courier New.ttf"),
        ]

        for candidate in font_candidates:
            if candidate.exists():
                try:
                    return image_font_module.truetype(str(candidate), size=size)
                except OSError:
                    continue

        return image_font_module.load_default()
