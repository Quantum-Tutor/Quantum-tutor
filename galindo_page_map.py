import os


GALINDO_IMAGE_PAGE_OFFSET = int(os.getenv("GALINDO_IMAGE_PAGE_OFFSET", "15"))
GALINDO_OCR_PAGE_DELTA = 1


def _as_positive_int(value) -> int | None:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def galindo_asset_page_from_display(display_page) -> int | None:
    display_page_int = _as_positive_int(display_page)
    if display_page_int is None:
        return None
    return display_page_int + GALINDO_IMAGE_PAGE_OFFSET


def galindo_display_page_from_asset(asset_page) -> int | None:
    asset_page_int = _as_positive_int(asset_page)
    if asset_page_int is None:
        return None
    display_page = asset_page_int - GALINDO_IMAGE_PAGE_OFFSET
    return display_page if display_page > 0 else None


def galindo_asset_page_from_ocr(ocr_page) -> int | None:
    ocr_page_int = _as_positive_int(ocr_page)
    if ocr_page_int is None:
        return None
    return ocr_page_int + GALINDO_OCR_PAGE_DELTA


def galindo_display_page_from_ocr(ocr_page) -> int | None:
    asset_page = galindo_asset_page_from_ocr(ocr_page)
    return galindo_display_page_from_asset(asset_page)


def resolve_galindo_reference(
    *,
    display_page=None,
    asset_page=None,
    ocr_page=None,
) -> dict:
    display_page_int = _as_positive_int(display_page)
    asset_page_int = _as_positive_int(asset_page)
    ocr_page_int = _as_positive_int(ocr_page)

    if asset_page_int is None:
        if ocr_page_int is not None:
            asset_page_int = galindo_asset_page_from_ocr(ocr_page_int)
        elif display_page_int is not None:
            asset_page_int = galindo_asset_page_from_display(display_page_int)

    if display_page_int is None:
        if asset_page_int is not None:
            display_page_int = galindo_display_page_from_asset(asset_page_int)
        elif ocr_page_int is not None:
            display_page_int = galindo_display_page_from_ocr(ocr_page_int)

    if ocr_page_int is None and asset_page_int is not None:
        candidate_ocr_page = asset_page_int - GALINDO_OCR_PAGE_DELTA
        ocr_page_int = candidate_ocr_page if candidate_ocr_page > 0 else None

    return {
        "display_page": display_page_int,
        "asset_page": asset_page_int,
        "ocr_page": ocr_page_int,
        "image_id": f"page_{asset_page_int}" if asset_page_int is not None else None,
        "image_filename": f"page_{asset_page_int}.png" if asset_page_int is not None else None,
    }
