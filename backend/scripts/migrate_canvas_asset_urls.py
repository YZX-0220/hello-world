import json
import os
import re
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "app.db")

# 匹配所有包含 /api/v1/assets/xxx/content 的 URL 格式（带或不带域名）
ASSET_URL_REGEX = re.compile(r"^(?:https?://[^/]+)?/api/v1/assets/([^/]+)/content")


def clean_node(node: dict) -> bool:
    changed = False
    url = node.get("url")
    asset_id = node.get("asset_id")

    if url:
        match = ASSET_URL_REGEX.search(url)
        if match:
            extracted_id = match.group(1)
            if not asset_id:
                node["asset_id"] = extracted_id
                changed = True
            canonical_path = f"/api/v1/assets/{extracted_id}/content"
            if url != canonical_path:
                node["url"] = canonical_path
                changed = True
        elif url.startswith("http://") or url.startswith("https://"):
            # 如果是其他带域名的地址但匹配本站资产路由
            if "/api/v1/assets/" in url and "/content" in url:
                parts = url.split("/api/v1/assets/")[1].split("/content")[0]
                node["asset_id"] = parts
                node["url"] = f"/api/v1/assets/{parts}/content"
                changed = True
    elif asset_id and not url:
        # 如果有 asset_id 但没有 url，补全相对路径
        node["url"] = f"/api/v1/assets/{asset_id}/content"
        changed = True

    return changed


def migrate_database():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. 迁移 video_projects 表中的 canvas_data_json
    print("Checking video_projects...")
    cursor.execute(
        "SELECT id, canvas_data_json FROM video_projects WHERE canvas_data_json IS NOT NULL"
    )
    projects = cursor.fetchall()
    updated_projects = 0
    for proj_id, canvas_json in projects:
        try:
            data = json.loads(canvas_json)
        except Exception:
            continue

        doc_changed = False
        nodes = data.get("nodes", [])
        if isinstance(nodes, list):
            for node in nodes:
                if clean_node(node):
                    doc_changed = True

        # 还要检查 generation_snapshot, generation_review 等嵌套 sources
        for key in ("generation_snapshot",):
            snapshot = data.get(key, [])
            if isinstance(snapshot, list):
                for node in snapshot:
                    if clean_node(node):
                        doc_changed = True

        if doc_changed:
            new_json = json.dumps(data, ensure_ascii=False)
            cursor.execute(
                "UPDATE video_projects SET canvas_data_json = ? WHERE id = ?", (new_json, proj_id)
            )
            updated_projects += 1

    print(f"Updated {updated_projects} video_projects.")

    # 2. 迁移 video_project_versions 表中的 generation_review_json
    print("Checking video_project_versions...")
    cursor.execute(
        "SELECT id, generation_review_json FROM video_project_versions WHERE generation_review_json IS NOT NULL"
    )
    versions = cursor.fetchall()
    updated_versions = 0
    for ver_id, review_json in versions:
        try:
            data = json.loads(review_json)
        except Exception:
            continue

        review_changed = False
        sources = data.get("sources", [])
        if isinstance(sources, list):
            for node in sources:
                if clean_node(node):
                    review_changed = True

        if review_changed:
            new_json = json.dumps(data, ensure_ascii=False)
            cursor.execute(
                "UPDATE video_project_versions SET generation_review_json = ? WHERE id = ?",
                (new_json, ver_id),
            )
            updated_versions += 1

    print(f"Updated {updated_versions} video_project_versions.")

    conn.commit()
    conn.close()
    print("Migration finished successfully.")


if __name__ == "__main__":
    migrate_database()
