"""Routes Pixel Office Suite — Access, Word, Excel."""


def register_office_routes(app):
    """Enregistre toutes les routes de la suite bureautique."""

    # ─── Page d'accueil de la Suite ────────────────────

    @app.route("/office")
    def office_home():
        from flask import render_template
        return render_template("office/index.html")

    # ─── Pixel Access ──────────────────────────────────

    @app.route("/office/access")
    def office_access():
        from flask import render_template
        return render_template("office/access.html")

    @app.route("/api/office/access/tables")
    def api_access_tables():
        from core.office.access import access_db
        return {"tables": access_db.list_tables()}

    @app.route("/api/office/access/table/<name>")
    def api_access_table(name):
        from flask import request
        from core.office.access import access_db
        limit = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int)
        data = access_db.get_table(name, limit=limit, offset=offset)
        if data:
            return data
        return {"status": "error", "message": "Table introuvable"}, 404

    @app.route("/api/office/access/query", methods=["POST"])
    def api_access_query():
        from flask import request
        from core.office.access import access_db
        data = request.get_json(force=True)
        return access_db.execute_query(data.get("sql", ""))

    @app.route("/api/office/access/insert/<table>", methods=["POST"])
    def api_access_insert(table):
        from flask import request
        from core.office.access import access_db
        data = request.get_json(force=True)
        return access_db.insert(table, data)

    @app.route("/api/office/access/export/<table>/<fmt>")
    def api_access_export(table, fmt):
        from core.office.access import access_db
        if fmt == "csv":
            csv_data = access_db.export_csv(table)
            if csv_data:
                from flask import Response
                return Response(csv_data, mimetype="text/csv",
                                headers={"Content-Disposition": f"attachment; filename={table}.csv"})
        elif fmt == "json":
            json_data = access_db.export_json(table)
            if json_data:
                from flask import Response
                return Response(json_data, mimetype="application/json",
                                headers={"Content-Disposition": f"attachment; filename={table}.json"})
        return {"status": "error"}, 404

    @app.route("/api/office/access/stats")
    def api_access_stats():
        from core.office.access import access_db
        return access_db.stats()

    # ─── Pixel Word ────────────────────────────────────

    @app.route("/office/word")
    def office_word():
        from flask import render_template
        return render_template("office/word.html")

    @app.route("/api/office/word/templates")
    def api_word_templates():
        from core.office.word import word
        return {"templates": word.list_templates()}

    @app.route("/api/office/word/create", methods=["POST"])
    def api_word_create():
        from flask import request
        from core.office.word import word
        data = request.get_json(force=True)
        doc = word.create_from_template(
            template_id=data.get("template", "blank"),
            title=data.get("title", "Document"),
            author=data.get("author", ""),
            fields=data.get("fields", {}),
            tags=data.get("tags", []),
        )
        if doc:
            word.save(doc)
            return {"status": "ok", "doc_id": doc.doc_id}
        return {"status": "error"}, 400

    @app.route("/api/office/word/save", methods=["POST"])
    def api_word_save():
        from flask import request
        from core.office.word import word
        import json
        data = request.get_json(force=True)
        doc = word.open(data.get("doc_id", ""))
        if doc:
            doc.content = data.get("content", doc.content)
            doc.title = data.get("title", doc.title)
            doc.modified = __import__("datetime").datetime.now().isoformat()
            word.save(doc)
            return {"status": "ok"}
        return {"status": "error", "message": "Document introuvable"}, 404

    @app.route("/api/office/word/open/<doc_id>")
    def api_word_open(doc_id):
        from core.office.word import word
        doc = word.open(doc_id)
        if doc:
            return {
                "status": "ok",
                "document": {
                    "doc_id": doc.doc_id,
                    "title": doc.title,
                    "content": doc.content,
                    "author": doc.author,
                    "template": doc.template,
                    "modified": doc.modified,
                },
                "rendered": word.render_markdown(doc),
            }
        return {"status": "error"}, 404

    @app.route("/api/office/word/list")
    def api_word_list():
        from flask import request
        from core.office.word import word
        category = request.args.get("category", "")
        author = request.args.get("author", "")
        return {"documents": word.list(category=category, author=author)}

    # ─── Pixel Excel ───────────────────────────────────

    @app.route("/office/excel")
    def office_excel():
        from flask import render_template
        return render_template("office/excel.html")

    @app.route("/api/office/excel/sheet", methods=["POST"])
    def api_excel_sheet():
        from flask import request
        from core.office.excel import excel_engine
        data = request.get_json(force=True)
        sheet = excel_engine.create_sheet(
            name=data.get("name", "Sheet1"),
            rows=data.get("rows", 100),
            cols=data.get("cols", 26),
        )
        return {"status": "ok", "sheet": excel_engine.to_dict(sheet)}

    @app.route("/api/office/excel/cell", methods=["POST"])
    def api_excel_cell():
        from flask import request
        from core.office.excel import excel_engine
        data = request.get_json(force=True)
        sheet_data = data.get("sheet", {})
        sheet = excel_engine.from_dict(sheet_data)
        ref = data.get("ref", "A1")
        value = data.get("value")
        formula = data.get("formula", "")
        cell = excel_engine.set_cell(sheet, ref, value=value, formula=formula)
        return {
            "status": "ok",
            "cell": {"ref": ref, "value": cell.value, "formatted": cell.formatted,
                     "error": cell.error},
            "sheet": excel_engine.to_dict(sheet),
        }

    @app.route("/api/office/excel/formula", methods=["POST"])
    def api_excel_formula():
        from flask import request
        from core.office.excel import excel_engine
        data = request.get_json(force=True)
        sheet_data = data.get("sheet", {})
        sheet = excel_engine.from_dict(sheet_data)
        formula = data.get("formula", "")
        result = excel_engine.eval_formula(sheet, formula)
        return result

    @app.route("/api/office/excel/import-sensor", methods=["POST"])
    def api_excel_import_sensor():
        from flask import request
        from core.office.excel import excel_engine
        data = request.get_json(force=True)
        sheet_data = data.get("sheet", {})
        sheet = excel_engine.from_dict(sheet_data)
        result = excel_engine.import_sensor_data(
            sheet, data.get("sensor_id", ""),
            metric=data.get("metric", ""),
            days=data.get("days", 7),
        )
        return {**result, "sheet": excel_engine.to_dict(sheet)}

    @app.route("/api/office/excel/chart", methods=["POST"])
    def api_excel_chart():
        from flask import request
        from core.office.excel import excel_engine
        data = request.get_json(force=True)
        sheet_data = data.get("sheet", {})
        sheet = excel_engine.from_dict(sheet_data)
        chart = excel_engine.create_chart(
            sheet,
            chart_type=data.get("chart_type", "line"),
            data_range=data.get("data_range", ""),
            title=data.get("title", ""),
        )
        chart_data = excel_engine.chart_data(sheet, data.get("data_range", ""))
        return {"chart": chart, "data": chart_data}

    # ─── Clipboard (presse-papier) ────────────────────

    @app.route("/api/office/clipboard/copy", methods=["POST"])
    def api_clipboard_copy():
        from flask import request
        from core.office.clipboard import clipboard
        data = request.get_json(force=True)
        clip = clipboard.copy(
            data_type=data.get("data_type", "text"),
            source_app=data.get("source_app", "word"),
            content=data.get("content", {}),
        )
        return {"status": "ok", "clipboard_id": clip.clipboard_id}

    @app.route("/api/office/clipboard/paste")
    def api_clipboard_paste():
        from flask import request
        from core.office.clipboard import clipboard
        target = request.args.get("as", "")
        if target:
            data = clipboard.paste_as(target)
        else:
            clip = clipboard.paste()
            data = clip.content if clip else None
        if data:
            return {"status": "ok", "data": data}
        return {"status": "empty"}
