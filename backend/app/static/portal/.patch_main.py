"""Script to patch main.py with the portal redirect route."""
import pathlib

main_path = pathlib.Path(__file__).parent.parent.parent / "main.py"
content = main_path.read_text(encoding="utf-8")

OLD = '    app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")'
NEW = '''
    # Public student portal: /portal redirects to /portal/ so StaticFiles serves portal/index.html
    @app.get("/portal", tags=["Portal"], include_in_schema=False)
    def portal_redirect():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/portal/", status_code=302)

    app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")'''

if OLD in content:
    content = content.replace(OLD, NEW)
    main_path.write_text(content, encoding="utf-8")
    print("PATCHED OK")
else:
    print("TARGET NOT FOUND in main.py")
    print("--- checking content around mount ---")
    for i, line in enumerate(content.splitlines(), 1):
        if "mount" in line or "StaticFiles" in line:
            print(f"{i}: {repr(line)}")
