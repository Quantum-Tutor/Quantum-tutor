from pathlib import Path

from reference_visualizer import ReferenceVisualizer


def test_reference_visualizer_maps_galindo_display_page_to_asset_page(tmp_path):
    references_dir = tmp_path / "static_web" / "references"
    references_dir.mkdir(parents=True)
    cached_image = references_dir / "page_155.png"
    cached_image.write_bytes(b"png-cache")

    visualizer = ReferenceVisualizer(
        str(tmp_path / "missing.pdf"),
        output_dir=str(references_dir),
        base_dir=str(tmp_path),
    )

    resolved_path = visualizer.get_page_image(140)

    assert resolved_path == str(cached_image)
