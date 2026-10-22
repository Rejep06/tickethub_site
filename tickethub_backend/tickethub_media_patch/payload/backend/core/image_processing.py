"""Image policy shared by Admin, REST uploads and URL imports. No Django dependency."""
from tempfile import SpooledTemporaryFile
import math
import re
import uuid
import warnings
import xml.etree.ElementTree as ET
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SIDE = 20_000
MAX_PIXELS = 300_000_000
MAX_BYTES = 100 * 1024 * 1024
MAX_SVG_BYTES = 10 * 1024 * 1024
# A finite process-wide ceiling, never disable Pillow's decompression-bomb protection.
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class ImageError(ValueError):
    pass


def check_dimensions(width, height):
    if not all(math.isfinite(v) and v > 0 for v in (width, height)):
        raise ImageError('Некорректные размеры изображения.')
    if max(width, height) > MAX_SIDE:
        raise ImageError('Максимальная сторона изображения — 20 000 пикселей.')
    if width * height > MAX_PIXELS:
        raise ImageError('Максимальная площадь изображения — 300 МП.')


SVG_NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', SVG_NS)
TAGS = {'svg', 'g', 'defs', 'path', 'rect', 'circle', 'ellipse', 'line', 'polyline',
        'polygon', 'text', 'tspan', 'title', 'desc', 'linearGradient', 'radialGradient',
        'stop', 'clipPath'}
ATTRS = {'id', 'class', 'viewBox', 'width', 'height', 'x', 'y', 'x1', 'y1', 'x2', 'y2',
         'cx', 'cy', 'r', 'rx', 'ry', 'dx', 'dy', 'd', 'points', 'transform',
         'preserveAspectRatio', 'gradientUnits', 'gradientTransform', 'spreadMethod',
         'offset', 'fx', 'fy', 'fr', 'clipPathUnits', 'textLength', 'lengthAdjust',
         'rotate', 'version'}
STYLE = {'fill', 'fill-opacity', 'fill-rule', 'stroke', 'stroke-width', 'stroke-opacity',
         'stroke-linecap', 'stroke-linejoin', 'stroke-miterlimit', 'stroke-dasharray',
         'stroke-dashoffset', 'opacity', 'font-family', 'font-size', 'font-weight',
         'font-style', 'text-anchor', 'dominant-baseline', 'letter-spacing',
         'word-spacing', 'stop-color', 'stop-opacity', 'clip-rule', 'clip-path',
         'visibility', 'display', 'vector-effect', 'color', 'paint-order'}
ID = re.compile(r'[A-Za-z_][\w.:-]*\Z', re.ASCII)
LOCAL_URL = re.compile(r'url\(\s*#([A-Za-z_][\w.:-]*)\s*\)\Z', re.ASCII | re.I)


def _name(tag):
    return tag.rsplit('}', 1)[-1]


def _safe_value(value):
    if len(value) > 100_000 or any(ord(c) < 32 and c not in '\t\n\r' for c in value):
        raise ImageError('Слишком сложный SVG.')
    lowered = value.lower()
    if any(c in value for c in ['\\', '<', '>', '@', '{', '}']):
        raise ImageError('Недопустимое значение SVG/CSS.')
    if any(s in lowered for s in ['javascript:', 'data:', 'http:', 'https:', 'expression', 'var(', '/*']):
        raise ImageError('Внешние ресурсы и исполняемый код в SVG запрещены.')
    if 'url' in lowered and not LOCAL_URL.fullmatch(value.strip()):
        raise ImageError('В SVG разрешены только локальные ссылки url(#id).')
    return value.strip()


def _declarations(text):
    result = {}
    for declaration in text.split(';'):
        if not declaration.strip():
            continue
        if ':' not in declaration:
            raise ImageError('Некорректный стиль SVG.')
        key, value = (s.strip() for s in declaration.split(':', 1))
        if key not in STYLE:
            raise ImageError(f'Неподдерживаемое свойство SVG: {key[:60]}.')
        result[key] = _safe_value(value)
    return result


def _length(value):
    match = re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)(px|pt|pc|mm|cm|in)?', value.strip())
    if not match:
        raise ImageError('Задайте размеры SVG в пикселях либо корректный viewBox.')
    factor = {None: 1, 'px': 1, 'pt': 96 / 72, 'pc': 16, 'mm': 96 / 25.4, 'cm': 96 / 2.54, 'in': 96}[match[2]]
    return float(match[1]) * factor


def sanitize_svg(body):
    """Accept a static SVG subset; rebuild XML, never serve the original document."""
    if len(body) > MAX_SVG_BYTES:
        raise ImageError('SVG должен занимать не более 10 МиБ.')
    try:
        text = body.decode('utf-8-sig')
    except UnicodeError:
        raise ImageError('SVG должен быть в UTF-8.') from None
    # Reject DTD/XXE, entities and processing instructions before XML parsing.
    if re.search(r'<!\s*(DOCTYPE|ENTITY)', text, re.I) or re.search(r'<\?(?!xml\s)', text, re.I):
        raise ImageError('DTD, ENTITY и внешние инструкции в SVG запрещены.')
    try:
        root = ET.fromstring(text)
    except (ET.ParseError, RecursionError):
        raise ImageError('Некорректный SVG/XML.') from None
    if root.tag not in {'svg', '{' + SVG_NS + '}svg'}:
        raise ImageError('Ожидается документ SVG, не HTML.')
    nodes = list(root.iter())
    if len(nodes) > 100_000:
        raise ImageError('SVG содержит более 100 000 элементов.')
    classes, id_styles, ids = {}, {}, set()
    for node in nodes:
        name = _name(node.tag)
        if name in {'script', 'foreignObject', 'image', 'use', 'animate', 'animateTransform', 'animateMotion', 'set', 'iframe', 'a'}:
            raise ImageError(f'Элемент {name} не поддерживается: нужен статический SVG без активных/внешних ресурсов.')
        for key, value in node.attrib.items():
            if _name(key).lower().startswith('on') or _name(key) in {'href', 'base'}:
                raise ImageError('Обработчики событий и внешние ссылки в SVG запрещены.')
        identity = node.get('id')
        if identity:
            if not ID.fullmatch(identity) or identity in ids:
                raise ImageError('Некорректный или повторный id в SVG.')
            ids.add(identity)
        if name == 'style':
            css = re.sub(r'/\*.*?\*/', '', ''.join(node.itertext()), flags=re.S)
            matches = list(re.finditer(r'([^{}]+)\{([^{}]*)\}', css))
            if re.sub(r'([^{}]+)\{([^{}]*)\}', '', css).strip():
                raise ImageError('Неподдерживаемый CSS SVG.')
            for rule in matches:
                declarations = _declarations(rule[2])
                for selector in rule[1].split(','):
                    selector = selector.strip()
                    if not re.fullmatch(r'[.#][A-Za-z_][\w-]*', selector, re.ASCII):
                        raise ImageError('В SVG поддерживаются простые CSS-классы и id.')
                    target = classes if selector[0] == '.' else id_styles
                    target.setdefault(selector[1:], {}).update(declarations)
    box = root.get('viewBox')
    box_size = None
    if box:
        try:
            values = [float(x) for x in re.split(r'[\s,]+', box.strip())]
            if len(values) != 4 or not all(math.isfinite(x) for x in values) or min(values[2:]) <= 0:
                raise ValueError
            box_size = values[2:]
        except ValueError:
            raise ImageError('Некорректный viewBox SVG.') from None
    width, height = root.get('width'), root.get('height')
    w = _length(width) if width and not width.endswith('%') else (box_size[0] if box_size else None)
    h = _length(height) if height and not height.endswith('%') else (box_size[1] if box_size else None)
    if w is None or h is None:
        raise ImageError('У SVG должны быть размеры width/height или viewBox.')
    check_dimensions(w, h)

    def rebuild(node, depth=0):
        if depth > 64:
            raise ImageError('SVG имеет слишком глубокую вложенность.')
        name = _name(node.tag)
        if name in {'metadata', 'style'} or (node.tag.startswith('{') and not node.tag.startswith('{' + SVG_NS + '}')):
            return None
        if name not in TAGS:
            raise ImageError(f'Неподдерживаемый элемент SVG: {name[:60]}.')
        attrs = {}
        for key, value in node.attrib.items():
            if key in ATTRS or key in STYLE:
                attrs[key] = _safe_value(value)
        styles = {}
        for cls in node.get('class', '').split():
            styles.update(classes.get(cls, {}))
        styles.update(id_styles.get(node.get('id'), {}))
        styles.update(_declarations(node.get('style', '')))
        # Inline presentation properties preserve only the validated static CSS subset.
        if styles:
            attrs['style'] = ';'.join(f'{k}:{v}' for k, v in styles.items())
        out = ET.Element('{' + SVG_NS + '}' + name, attrs)
        if name in {'text', 'tspan', 'title', 'desc'}:
            out.text = node.text
        for child in node:
            result = rebuild(child, depth + 1)
            if result is not None:
                out.append(result)
                if name in {'text', 'tspan'}:
                    result.tail = child.tail
        return out
    result = rebuild(root)
    result.set('width', f'{w:g}')
    result.set('height', f'{h:g}')
    # References must be local and of a harmless type. No recursive use/mask/filter graphs.
    for clip in result.iter('{' + SVG_NS + '}clipPath'):
        for child in clip.iter():
            if child.get('clip-path') or 'clip-path:' in child.get('style', ''):
                raise ImageError('Рекурсивные/вложенные clip-path в SVG не поддерживаются.')
    targets = {node.get('id'): _name(node.tag) for node in result.iter() if node.get('id')}
    for node in result.iter():
        for key, value in node.attrib.items():
            for target in re.findall(r'url\(\s*#([\w.:-]+)\s*\)', value):
                if targets.get(target) not in {'linearGradient', 'radialGradient', 'clipPath'}:
                    raise ImageError('SVG ссылается на неизвестный ресурс.')
                if _name(node.tag) in {'clipPath', 'defs'}:
                    raise ImageError('Вложенные ссылки SVG не поддерживаются.')
    return ET.tostring(result, encoding='utf-8', xml_declaration=True)


def process_image(stream, size):
    """Return (seekable temporary file, UUID name). No resize, no metadata pass-through."""
    if size <= 0 or size > MAX_BYTES:
        raise ImageError('Максимальный размер файла — 100 МиБ.')
    stream.seek(0)
    prefix = stream.read(1024).lstrip(b'\xef\xbb\xbf \t\r\n')
    stream.seek(0)
    output = SpooledTemporaryFile(max_size=1024 * 1024, mode='w+b')
    try:
        if prefix.startswith(b'<'):
            output.write(sanitize_svg(stream.read(MAX_SVG_BYTES + 1)))
            extension = 'svg'
        else:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(stream, formats=['JPEG', 'PNG', 'WEBP']) as original:
                    check_dimensions(original.width, original.height)
                    if getattr(original, 'n_frames', 1) != 1:
                        raise ImageError('Анимированные изображения не поддерживаются.')
                    original.load()
                    # exif_transpose(in_place=True) avoids an unnecessary full-size copy.
                    ImageOps.exif_transpose(original, in_place=True)
                    has_alpha = 'A' in original.getbands() or 'transparency' in original.info
                    mode = 'RGBA' if has_alpha else 'RGB'
                    converted = original if original.mode == mode else original.convert(mode)
                    try:
                        converted.info.clear()
                        extension, fmt = ('png', 'PNG') if has_alpha else ('jpg', 'JPEG')
                        converted.save(output, format=fmt, **({'quality': 90} if fmt == 'JPEG' else {}))
                    finally:
                        if converted is not original:
                            converted.close()
        if output.tell() > MAX_BYTES:
            raise ImageError('После проверки файл превышает 100 МиБ; используйте более компактное изображение.')
        output.seek(0)
        return output, f'{uuid.uuid4()}.{extension}'
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning, MemoryError) as exc:
        output.close()
        raise ImageError('Не удалось обработать изображение: неверный формат, лимит или недостаточно памяти.') from exc
    except Exception:
        output.close()
        raise
    finally:
        stream.seek(0)
