import pytest
from app.schemas.canvas import CanvasNode, CanvasDocument


def test_canvas_node_asset_id_and_url():
    node = CanvasNode(
        id="node_1",
        type="image",
        title="Test Node",
        asset_id="asset_123",
        url="/api/v1/assets/asset_123/content",
    )
    assert node.asset_id == "asset_123"
    assert node.url == "/api/v1/assets/asset_123/content"


def test_canvas_document_with_asset_id():
    doc = CanvasDocument(
        nodes=[
            CanvasNode(
                id="node_1",
                type="image",
                title="Test Image",
                asset_id="asset_abc",
                url="/api/v1/assets/asset_abc/content",
            )
        ],
        connections=[],
    )
    data = doc.to_data()
    assert data["nodes"][0]["asset_id"] == "asset_abc"
    assert data["nodes"][0]["url"] == "/api/v1/assets/asset_abc/content"
