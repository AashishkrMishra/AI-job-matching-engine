from pypdf import PdfReader
import docx

# Tried in order. utf-8-sig comes first because it also strips the BOM that
# Notepad writes by default on Windows; cp1252 catches resumes exported from
# Word as plain text, which otherwise fail on a single smart quote.
_TEXT_ENCODINGS = ("utf-8-sig", "cp1252")

_UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")


def read_pdf(file):
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text


def read_docx(file):
    document = docx.Document(file)
    text = "\n".join([para.text for para in document.paragraphs])
    return text


def read_txt(file):
    raw = file.read()

    # UTF-16 has to be settled before the cascade below, because cp1252 cannot
    # fail on UTF-16 input: every byte maps to some character, NUL included. So
    # a UTF-16 resume would decode into NUL-interleaved mojibake, match zero
    # skills, and — since nothing raises — be reported as a confident 0% rather
    # than an error. Notepad's "Unicode" save option writes exactly this.
    if raw[:2] in _UTF16_BOMS:
        return raw.decode("utf-16")

    # No BOM, but NUL bytes: not valid text in any encoding tried below, while
    # ASCII-range UTF-16 is half NULs by construction. Endianness has to be
    # inferred rather than attempted, because utf-16-le and utf-16-be both decode
    # the same bytes without error — one of them into nonsense. Mostly-ASCII text
    # puts its NUL padding at even offsets in big-endian, odd in little-endian.
    if b"\x00" in raw:
        at_even = raw[0::2].count(0)
        at_odd = raw[1::2].count(0)
        try:
            return raw.decode("utf-16-be" if at_even > at_odd else "utf-16-le")
        except UnicodeDecodeError:
            pass

    for encoding in _TEXT_ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue

    # Last resort: keep the readable text rather than reject the whole file. The
    # result only feeds keyword matching, so a few replacement chars cost nothing.
    return raw.decode("utf-8", errors="replace")
