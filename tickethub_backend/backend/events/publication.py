"""Content checks shared by API, admin and the pre-launch catalogue audit.

Nothing here guesses a real category or rewrites an imported description.
"""
import re

PLACEHOLDER_CATEGORY_SLUGS = frozenset({"external-review"})
TEMPLATE_TOKEN = re.compile(r"\{\{?\s*[\w][\w .:-]{0,80}\s*\}?\}", re.UNICODE)
SOURCE_SALES_COPY = re.compile(
    r"(?:купить|бронирован|заказ|buy|book)[^\n]{0,120}(?:portalbilet|порталбилет)"
    r"|(?:portalbilet|порталбилет)[^\n]{0,120}(?:купить|бронирован|заказ|buy|book)", re.I)
PLACEHOLDER_NAME = re.compile(r"проверить категори|review category|не определен|не определён|uncategori[sz]ed", re.I)


def is_placeholder_category(category):
    return bool(
        getattr(category, "is_placeholder", False)
        or getattr(category, "slug", "") in PLACEHOLDER_CATEGORY_SLUGS
        or PLACEHOLDER_NAME.search(getattr(category, "name_ru", ""))
        or PLACEHOLDER_NAME.search(getattr(category, "name_en", ""))
    )


def content_issues(event):
    """Return field errors; called before publication, never from a client render."""
    errors = {}
    category = getattr(event, "category", None)
    if not category or is_placeholder_category(category):
        errors["category"] = "Выберите конкретную категорию: например, хоккей, футбол или концерт. Служебная категория импорта не подходит для публикации."
    elif not category.is_active:
        errors["category"] = "Категория выключена. Выберите активную категорию."
    elif getattr(category, "parent_id", None):
        visited = {category.pk}
        node = category.parent
        while node and node.pk not in visited:
            if not node.is_active or is_placeholder_category(node):
                errors["category"] = "Родительская категория выключена или служебная. Исправьте дерево категорий."
                break
            visited.add(node.pk)
            node = node.parent
    for field in ("title_ru", "title_en", "description_ru", "description_en"):
        value = getattr(event, field, "") or ""
        tokens = list(dict.fromkeys(TEMPLATE_TOKEN.findall(value)))
        if tokens:
            errors[field] = "Заполните или удалите шаблонные вставки: " + ", ".join(tokens[:5])
        elif SOURCE_SALES_COPY.search(value):
            errors[field] = "В тексте осталась инструкция покупки у источника импорта. Отредактируйте описание для Tickethub."
    return errors
