import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO


class InvoiceScanError(Exception):
    pass


def _text_from_pdf(data):
    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(data))
    except Exception as exc:
        raise InvoiceScanError('PDF se nepodařilo otevřít. Zkuste ho uložit znovu nebo použijte fotografii.') from exc
    if reader.is_encrypted:
        raise InvoiceScanError('PDF je chráněné heslem. Použijte nechráněný soubor nebo fotografii.')
    if len(reader.pages) > 3:
        raise InvoiceScanError('Faktura může mít nejvýše 3 strany.')

    extracted = '\n\n'.join((page.extract_text() or '').strip() for page in reader.pages).strip()
    if len(re.sub(r'\s+', '', extracted)) >= 80:
        return extracted
    raise InvoiceScanError(
        'PDF neobsahuje čitelný text. Otevřete první stranu a použijte volbu Vyfotit fakturu.'
    )


def extract_text(document):
    data = document.read()
    if not data:
        raise InvoiceScanError('Soubor je prázdný.')
    if not data.startswith(b'%PDF'):
        raise InvoiceScanError('Fotografie se musí nejprve přečíst přímo v telefonu.')
    text = _text_from_pdf(data)
    if len(re.sub(r'\s+', '', text)) < 20:
        raise InvoiceScanError('Na snímku se nepodařilo najít dostatek textu. Vyfoťte fakturu rovně, zblízka a za lepšího světla.')
    return text.strip()


def _lines(text):
    return [re.sub(r'\s+', ' ', line).strip() for line in text.splitlines() if line.strip()]


def _fold(value):
    return ''.join(character for character in unicodedata.normalize('NFKD', value) if not unicodedata.combining(character))


def _value_after_label(lines, labels, max_length=120):
    label_pattern = _fold('|'.join(labels))
    for index, line in enumerate(lines):
        match = re.search(rf'(?i)(?:{label_pattern})\s*[:#]?\s*(.+)$', _fold(line))
        if match and match.group(1).strip():
            return line[match.start(1):match.end(1)].strip()[:max_length]
        if re.search(rf'(?i)(?:{label_pattern})\s*[:#]?$', _fold(line)) and index + 1 < len(lines):
            return lines[index + 1][:max_length]
    return ''


def _date_after_label(lines, labels):
    label_pattern = _fold('|'.join(labels))
    date_pattern = r'(\d{1,2}\s*[.\-/]\s*\d{1,2}\s*[.\-/]\s*[,;]?\s*\d{2,4})'
    for index, line in enumerate(lines):
        if not re.search(rf'(?i)(?:{label_pattern})', _fold(line)):
            continue
        # OCR reads two-column headers by rows. A neighbouring date label can
        # therefore appear between this label and its value.
        candidates = lines[index:index + 4]
        for candidate in candidates:
            match = re.search(date_pattern, candidate)
            if not match:
                continue
            value = re.sub(r'[\s,;]+', '', match.group(1)).replace('/', '.').replace('-', '.')
            for date_format in ('%d.%m.%Y', '%d.%m.%y'):
                try:
                    return datetime.strptime(value, date_format).date()
                except ValueError:
                    pass
    return None


def _decimal_from_text(value):
    cleaned = re.sub(r'[^\d,.-]', '', value).replace('−', '-')
    if not cleaned:
        return None
    if ',' in cleaned:
        cleaned = cleaned.replace('.', '').replace(',', '.')
    elif cleaned.count('.') > 1:
        cleaned = cleaned.replace('.', '')
    try:
        return Decimal(cleaned).quantize(Decimal('0.01'))
    except InvalidOperation:
        return None


def _amount_after_label(lines, labels):
    label_pattern = _fold('|'.join(labels))
    amount_pattern = r'-?\d[\d\s.]*[,.]\d{2}|-?\d[\d\s.]{2,}'
    for index, line in reversed(list(enumerate(lines))):
        if not re.search(rf'(?i)(?:{label_pattern})', _fold(line)):
            continue
        candidates = [line]
        if index + 1 < len(lines):
            candidates.append(lines[index + 1])
        for candidate in candidates:
            amounts = re.findall(amount_pattern, candidate)
            if amounts:
                parsed = _decimal_from_text(amounts[-1])
                if parsed is not None:
                    return parsed
    return None


def _block_after_heading(lines, headings, stop_headings, limit=7):
    start = None
    for index, line in enumerate(lines):
        if any(re.search(_fold(pattern), _fold(line), re.I) for pattern in headings):
            start = index + 1
            break
    if start is None:
        return ''
    block = []
    for line in lines[start:start + limit]:
        if any(re.search(_fold(pattern), _fold(line), re.I) for pattern in stop_headings):
            break
        block.append(line)
    return '\n'.join(block)


def _format_item_lines(items):
    quantity_pattern = re.compile(
        r'(?i)^\d+(?:[,.]\d+)?\s*(?:ks|hod|h|m|m2|m²|m3|m³|kg|g|l|bal|sada|den|kpl)?$'
    )
    amount_pattern = re.compile(r'(?i)^-?\d[\d\s.]*[,.]\d{2}\s*(?:Kc|K|CZK|EUR|€)?$')
    formatted = []
    index = 0
    while index < len(items):
        if index + 3 < len(items):
            description, quantity, unit_price, total = items[index:index + 4]
            if (
                quantity_pattern.fullmatch(_fold(quantity))
                and amount_pattern.fullmatch(_fold(unit_price))
                and amount_pattern.fullmatch(_fold(total))
            ):
                formatted.append(f'{description} | {quantity} | {unit_price} | {total}')
                index += 4
                continue
        formatted.append(items[index])
        index += 1
    return '\n'.join(formatted)


def _remove_ocr_item_preamble(items):
    combined_item = re.compile(r'(?i)[A-Za-zÀ-ž].*\d[\d\s.]*[,.]\d{2}')
    first_item = next((index for index, line in enumerate(items) if combined_item.search(line)), None)
    if first_item and first_item > 0:
        return items[first_item:]
    return items


def _clean_invoice_number(value):
    value = re.sub(r'(?<=\d)\s+(?=\d)', '', value.strip())
    if not value or re.search(r'(?i)\.(?:pdf|jpe?g|png|webp|heic)\b', value):
        return ''
    for token in re.findall(r'[A-Za-z0-9][A-Za-z0-9./-]*', value):
        if sum(character.isdigit() for character in token) >= 3:
            return token[:80]
    return ''


def _invoice_number_after_label(lines):
    # Prefer an explicit invoice-number label. Browser OCR can first produce a
    # damaged generic heading (for example "FAKTURA Cislo ...") and then read
    # the same header correctly during its focused second pass.
    label_groups = (
        [r'č(?:íslo|\.)?\s*faktury', r'daňový\s*doklad\s*č(?:íslo|\.)?'],
        [r'faktura\s*(?:č(?:íslo|\.)?\s*)?'],
    )
    for labels in label_groups:
        label_pattern = _fold('|'.join(labels))
        for index, line in enumerate(lines):
            folded_line = _fold(line)
            match = re.search(rf'(?i)(?:{label_pattern})\s*[:#]?\s*(.+)$', folded_line)
            if match and match.group(1).strip():
                number = _clean_invoice_number(line[match.start(1):match.end(1)])
                if number:
                    return number
            if re.search(rf'(?i)(?:{label_pattern})\s*[:#]?$', folded_line) and index + 1 < len(lines):
                number = _clean_invoice_number(lines[index + 1])
                if number:
                    return number
    return ''


def _clean_numeric_symbol(value):
    value = re.sub(r'(?<=\d)\s+(?=\d)', '', value)
    match = re.search(r'(?<!\d)\d{4,10}(?!\d)', value)
    return match.group(0) if match else ''


def _clean_payment_method(value):
    if not value:
        return ''
    next_label = re.search(
        r'(?i)\b(?:DUZP|datum|cislo\s+uctu|konstantni\s+symbol|variabilni\s+symbol|polozky)\b',
        _fold(value),
    )
    if next_label:
        value = value[:next_label.start()]
    return value.strip(' :-')[:100]


def _split_parallel_party_row(line):
    folded = _fold(line)

    for pattern in (r'\bICO\b', r'\bDIC\b'):
        matches = list(re.finditer(pattern, folded, re.I))
        if len(matches) >= 2:
            split = matches[1].start()
            return line[:split].strip(), line[split:].strip()

    postal_codes = list(re.finditer(r'\b\d{3}\s?\d{2}\b', folded))
    if len(postal_codes) >= 2:
        split = postal_codes[1].start()
        return line[:split].strip(), line[split:].strip()

    job_marker = re.search(r'(?i)\bZakazka\b', folded)
    if job_marker and job_marker.start() > 0:
        split = job_marker.start()
        return line[:split].strip(), line[split:].strip()

    company_suffix = re.search(r'(?i)(?:\bs\.?\s*r\.?\s*o\.?|\ba\.?\s*s\.?)(?=\s|$)', folded)
    if company_suffix and folded[company_suffix.end():].strip(' .,-'):
        split = company_suffix.end()
        return line[:split].strip(), line[split:].strip()

    numbers = list(re.finditer(r'\b\d+[A-Za-z/]?\b', folded))
    if (
        len(numbers) >= 2
        and not postal_codes
        and not re.search(r'(?i)\b(?:datum|faktura|symbol|castka|cena)\b', folded)
    ):
        split = numbers[0].end()
        return line[:split].strip(), line[split:].strip()
    return None


def _parallel_party_blocks(lines):
    supplier_indexes = [index for index, line in enumerate(lines) if re.search(r'(?i)\bdodavatel\b', _fold(line))]
    customer_indexes = [index for index, line in enumerate(lines) if re.search(r'(?i)\b(?:odberatel|zakaznik)\b', _fold(line))]
    if not supplier_indexes or not customer_indexes:
        return None
    supplier_index = supplier_indexes[0]
    customer_index = customer_indexes[0]
    if abs(supplier_index - customer_index) > 1:
        return None

    stop_pattern = re.compile(
        r'(?i)^(?:faktura|cislo\s+faktury|variabilni\s+symbol|zakazka|datum|duzp|'
        r'forma\s+uhrady|zpusob\s+platby|cislo\s+uctu|polozk|prace\s+a\s+material)\b'
    )
    party_lines = []
    for line in lines[max(supplier_index, customer_index) + 1:]:
        if stop_pattern.search(_fold(line)):
            break
        party_lines.append(line)
        if len(party_lines) >= 16:
            break
    if len(party_lines) < 4:
        return None
    split_rows = [_split_parallel_party_row(line) for line in party_lines]
    if sum(row is not None for row in split_rows) >= 2:
        supplier_lines = []
        customer_lines = []
        for line, split_row in zip(party_lines, split_rows):
            if split_row:
                supplier_line, customer_line = split_row
                if supplier_line:
                    supplier_lines.append(supplier_line)
                if customer_line:
                    customer_lines.append(customer_line)
            elif re.search(r'(?i)^E-?mail\b', _fold(line)):
                supplier_lines.append(line)
            elif re.search(r'(?i)^Zakazka\b', _fold(line)):
                customer_lines.append(line)
        if supplier_lines and customer_lines:
            return supplier_lines, customer_lines
    return party_lines[::2], party_lines[1::2]


def _supplier_address(lines):
    excluded = re.compile(r'(?i)^(?:ICO|DIC|E-?mail|telefon|tel\.?|www)\b')
    return '\n'.join(line for line in lines[1:] if not excluded.search(_fold(line)))


def _clean_party_lines(lines):
    cleaned = []
    for line in lines:
        if re.search(r'(?i)^(?:ICO|DIC)\s*:', _fold(line)):
            line = re.sub(r'\s+[A-Za-zÀ-ž]$', '', line)
        cleaned.append(line)
    return cleaned


def parse_invoice_text(text):
    lines = _lines(text)
    invoice_number = _invoice_number_after_label(lines)
    variable_symbol = _clean_numeric_symbol(
        _value_after_label(lines, [r'variabilní\s*symbol', r'var\.?\s*symbol', r'v\.?\s*s\.?'], 80)
    )

    supplier_block = _block_after_heading(
        lines,
        [r'^dodavatel\b'],
        [r'^odběratel\b', r'^faktura\b', r'^daňový\s+doklad\b'],
    )
    supplier_lines = supplier_block.splitlines()
    supplier_name = supplier_lines[0] if supplier_lines else ''
    supplier_address = _supplier_address(supplier_lines)
    customer_header = _block_after_heading(
        lines,
        [r'^odběratel\b', r'^zákazník\b'],
        [r'^dodavatel\b', r'^forma\s+úhrady', r'^datum\b', r'^položk'],
    )

    parallel_parties = _parallel_party_blocks(lines)
    if parallel_parties:
        supplier_lines, customer_lines = parallel_parties
        supplier_lines = _clean_party_lines(supplier_lines)
        customer_lines = _clean_party_lines(customer_lines)
        supplier_name = supplier_lines[0] if supplier_lines else ''
        supplier_address = _supplier_address(supplier_lines)
        customer_header = '\n'.join(customer_lines)

    ico_source = _fold('\n'.join(supplier_lines) or supplier_block or text)
    ico_match = re.search(r'(?i)\bICO\s*[:]?\s*(\d[\d\s]{6,10}\d)', ico_source)
    supplier_company_id = re.sub(r'\s+', '', ico_match.group(1)) if ico_match else ''

    item_start = next((index for index, line in enumerate(lines) if re.search(r'(?i)^(polozk|popis|oznaceni\s+dodavky|prace\s+a\s+material)', _fold(line))), None)
    items = []
    if item_start is not None:
        item_header = re.compile(
            r'(?i)^(?:popis(?:\s+prace)?|polozka|polozky|oznaceni(?:\s+dodavky)?|'
            r'mnozstvi|m\.?\s*j\.?|jednotka|cena(?:\s+za)?|cena\s+za\s+jednotku|'
            r'jednotku|sazba|dph|celkem)$'
        )
        item_summary = re.compile(
            r'(?i)^(?:rekapitulace|zaklad\s+dane|zaklad\s+DPH|sazba\s+DPH|'
            r'castka\s+DPH|DPH\s+celkem|celkem\s+k\s*uhrade|k\s+uhrade)'
        )
        content_started = False
        for line in lines[item_start + 1:]:
            folded_line = _fold(line)
            if item_summary.search(folded_line):
                break
            if not content_started and item_header.fullmatch(folded_line):
                continue
            if content_started and re.search(r'(?i)^celkem\b', folded_line):
                break
            items.append(line)
            content_started = True

    return {
        'supplier_name': supplier_name,
        'supplier_company_id': supplier_company_id,
        'supplier_address': supplier_address,
        'customer_header': customer_header,
        'invoice_number': invoice_number,
        'variable_symbol': variable_symbol,
        'issue_date': _date_after_label(lines, [r'datum\s+vystavení', r'vystaveno']),
        'taxable_date': _date_after_label(lines, [r'datum\s+(?:uskutečnění\s+)?zdanitelného\s+plnění', r'DUZP']),
        'due_date': _date_after_label(lines, [r'datum\s+splatnosti', r'splatnost']),
        'payment_method': _clean_payment_method(
            _value_after_label(lines, [r'forma\s+úhrady', r'způsob\s+platby'], 160)
        ),
        'items_text': _format_item_lines(_remove_ocr_item_preamble(items)),
        'subtotal': _amount_after_label(lines, [r'základ\s+daně', r'základ\s+DPH']),
        'vat_amount': _amount_after_label(lines, [r'částka\s+DPH', r'DPH\s+celkem']),
        'total_amount': _amount_after_label(lines, [r'celkem\s+k\s+úhradě', r'k\s+úhradě', r'celková\s+částka', r'celkem']),
        'currency': 'EUR' if re.search(r'(?i)\bEUR\b|€', text) else 'CZK',
        'raw_text': text,
    }


def extract_invoice_data(document):
    return parse_invoice_text(extract_text(document))
