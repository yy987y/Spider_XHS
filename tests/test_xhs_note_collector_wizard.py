import importlib.util
import json
import os
import sys
from pathlib import Path


def load_launch_wizard():
    os.environ["XHS_NOTE_COLLECTOR_SKIP_BOOTSTRAP"] = "1"
    sys.dont_write_bytecode = True
    script_path = (
        Path(__file__).resolve().parents[1]
        / "skills"
        / "xhs-note-collector"
        / "scripts"
        / "launch_wizard.py"
    )
    spec = importlib.util.spec_from_file_location("launch_wizard", script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_bootstrap():
    sys.dont_write_bytecode = True
    script_path = (
        Path(__file__).resolve().parents[1]
        / "skills"
        / "xhs-note-collector"
        / "scripts"
        / "bootstrap.py"
    )
    spec = importlib.util.spec_from_file_location("bootstrap", script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_write_env_cookie_replaces_existing_cookie_without_touching_other_values(tmp_path):
    wizard = load_launch_wizard()
    env_path = tmp_path / ".env"
    env_path.write_text("FOO=bar\nCOOKIES=\"old\"\nBAZ=qux\n", encoding="utf-8")

    wizard._write_env_cookie(tmp_path, {"a1": "abc", "web_session": "session"})

    text = env_path.read_text(encoding="utf-8")
    assert "FOO=bar" in text
    assert "BAZ=qux" in text
    assert "COOKIES=" in text
    assert "a1=abc" in text
    assert "web_session=session" in text
    assert "old" not in text


def test_wizard_state_reuses_existing_env_cookie(tmp_path):
    wizard = load_launch_wizard()
    (tmp_path / ".env").write_text('COOKIES="a1=abc; web_session=session"\n', encoding="utf-8")

    state = wizard.WizardState(repo=tmp_path, output_dir=str(tmp_path))

    assert state.cookie_ready is True
    assert state.login_status == "已检测到本地 Cookie，将优先复用"


def test_wizard_page_contains_non_technical_flow_copy():
    wizard = load_launch_wizard()

    assert "小红书笔记采集向导" in wizard.PAGE_HTML
    assert "登录成功后会自动开始采集" in wizard.PAGE_HTML
    assert "重新生成二维码" in wizard.PAGE_HTML
    assert "开始采集并生成看板" in wizard.PAGE_HTML


def test_wizard_state_prefills_keywords_from_search_query(tmp_path):
    wizard = load_launch_wizard()

    state = wizard.WizardState(
        repo=tmp_path,
        output_dir=str(tmp_path),
        search_query="光子嫩肤 北京八大处",
        auto_start=True,
    )

    assert state.default_payload() == {
        "search_query": "光子嫩肤 北京八大处",
        "keywords": "光子嫩肤,北京八大处",
        "date_range": "recent_7_days",
        "max_search_candidates": 50,
        "auto_start": True,
    }


def test_wizard_default_max_search_candidates_is_50(tmp_path):
    wizard = load_launch_wizard()

    state = wizard.WizardState(repo=tmp_path, output_dir=str(tmp_path))

    assert state.default_payload()["max_search_candidates"] == 50
    assert 'id="summaryMax">50<' in wizard.PAGE_HTML
    assert 'id="maxCandidates" type="number" value="50"' in wizard.PAGE_HTML


def test_safe_task_name_removes_invalid_filename_characters():
    wizard = load_launch_wizard()

    assert wizard._safe_task_name("大超炮 北京/上海?") == "大超炮_北京上海"


def test_wizard_collect_enables_cdp_detail_export(monkeypatch, tmp_path):
    wizard = load_launch_wizard()
    captured = {}

    def fake_run_collection(**kwargs):
        captured.update(kwargs)
        return {
            "xlsx": tmp_path / "notes.xlsx",
            "html": tmp_path / "notes.html",
            "jsonl": tmp_path / "notes.jsonl",
            "log_jsonl": tmp_path / "notes.logs.jsonl",
            "details_dir": tmp_path / "details",
            "detail_jsonl": tmp_path / "details.jsonl",
            "detail_summary": tmp_path / "details.summary.json",
        }

    monkeypatch.setattr(wizard, "run_collection", fake_run_collection)
    state = wizard.WizardState(repo=tmp_path, output_dir=str(tmp_path))
    handler_cls = type("TestWizardHandler", (wizard.WizardHandler,), {"state": state})
    handler = object.__new__(handler_cls)
    handler.headers = {"Content-Length": "2"}
    handler.rfile = type("Body", (), {"read": lambda self, length: b"{}"})()
    responses = []
    monkeypatch.setattr(
        wizard,
        "_json_response",
        lambda _handler, payload, status=200: responses.append((status, payload)),
    )
    payload = {
        "search_query": "大超炮 北京",
        "keywords": "大超炮,北京",
        "date_range": "recent_7_days",
        "max_search_candidates": 20,
        "task_name": "大超炮 北京",
    }
    monkeypatch.setattr(handler, "_read_json", lambda: payload)

    handler._collect()

    assert captured["enrich_details"] is True
    assert captured.get("use_note_detail_api") is not True
    assert captured["cdp_profile_dir"].endswith("xhs-note-collector-chrome")
    assert responses[-1][0] == 200
    outputs = responses[-1][1]["outputs"]
    assert "details_dir" in outputs
    assert "detail_summary_url" in outputs


def test_wizard_collect_uses_state_defaults_when_form_payload_empty(monkeypatch, tmp_path):
    wizard = load_launch_wizard()
    captured = {}

    def fake_run_collection(**kwargs):
        captured.update(kwargs)
        return {
            "xlsx": tmp_path / "notes.xlsx",
            "html": tmp_path / "notes.html",
            "jsonl": tmp_path / "notes.jsonl",
            "log_jsonl": tmp_path / "notes.logs.jsonl",
        }

    monkeypatch.setattr(wizard, "run_collection", fake_run_collection)
    state = wizard.WizardState(
        repo=tmp_path,
        output_dir=str(tmp_path),
        search_query="光子嫩肤 北京八大处",
        keywords="光子嫩肤,北京八大处",
        auto_start=True,
    )
    handler_cls = type("TestWizardHandler", (wizard.WizardHandler,), {"state": state})
    handler = object.__new__(handler_cls)
    handler.headers = {"Content-Length": "2"}
    handler.rfile = type("Body", (), {"read": lambda self, length: b"{}"})()
    responses = []
    monkeypatch.setattr(
        wizard,
        "_json_response",
        lambda _handler, payload, status=200: responses.append((status, payload)),
    )
    monkeypatch.setattr(handler, "_read_json", lambda: {})

    handler._collect()

    assert captured["search_query"] == "光子嫩肤 北京八大处"
    assert captured["keywords"] == "光子嫩肤,北京八大处"
    assert captured["date_range_value"] == "recent_7_days"
    assert captured["max_search_candidates"] == 50
    assert responses[-1][0] == 200


def test_bootstrap_installs_missing_python_requirements(monkeypatch, tmp_path):
    bootstrap = load_bootstrap()
    repo = tmp_path
    (repo / "requirements.txt").write_text("requests\n", encoding="utf-8")
    (repo / "package.json").write_text("{}", encoding="utf-8")
    (repo / "node_modules").mkdir()

    calls = []
    missing_results = [["requests"], []]
    monkeypatch.setattr(bootstrap.sys, "version_info", (3, 10, 0))
    monkeypatch.setattr(bootstrap, "_missing_python_modules", lambda: missing_results.pop(0))
    monkeypatch.setattr(bootstrap, "_check_node", lambda _repo, install_system=True: None)
    monkeypatch.setattr(bootstrap, "find_chrome_executable", lambda: "/chrome")
    monkeypatch.setattr(bootstrap, "_run", lambda cmd, cwd: calls.append((cmd, cwd)))

    assert bootstrap.ensure_environment(repo) == repo
    assert calls == [([sys.executable, "-m", "pip", "install", "-r", str(repo / "requirements.txt")], repo)]


def test_bootstrap_defaults_to_bundled_runtime(monkeypatch):
    bootstrap = load_bootstrap()
    monkeypatch.delenv("XHS_NOTE_COLLECTOR_REPO", raising=False)

    repo = bootstrap.find_repo()

    assert repo.name == "runtime"
    assert repo.parent.name == "xhs-note-collector"
    assert (repo / "spider" / "collect_notes.py").exists()
    assert (repo / "apis" / "xhs_pc_login_apis.py").exists()
    assert (repo / "xhs_utils" / "xhs_util.py").exists()
    assert (repo / "static" / "xhs_main_260411.js").exists()
    assert (repo / "package.json").exists()


def test_bundled_runtime_does_not_include_local_outputs_or_cache():
    runtime = (
        Path(__file__).resolve().parents[1]
        / "skills"
        / "xhs-note-collector"
        / "runtime"
    )

    assert runtime.exists()
    assert not (runtime / "datas").exists()
    assert not (runtime / "node_modules").exists()
    assert not list(runtime.rglob("__pycache__"))


def test_launch_wizard_repo_default_is_internal_runtime():
    wizard = load_launch_wizard()

    assert wizard.REPO_ROOT.name == "runtime"
    assert wizard.REPO_ROOT.parent.name == "xhs-note-collector"


def test_bootstrap_reports_missing_node_without_terminal_noise(monkeypatch, tmp_path):
    bootstrap = load_bootstrap()
    repo = tmp_path
    monkeypatch.setattr(bootstrap.sys, "version_info", (3, 10, 0))
    monkeypatch.setattr(bootstrap, "_missing_python_modules", lambda: [])
    monkeypatch.setattr(bootstrap.shutil, "which", lambda name: None)

    try:
        bootstrap.ensure_environment(repo)
    except bootstrap.BootstrapError as exc:
        assert "未找到 Node.js/npm" in str(exc)
    else:
        raise AssertionError("expected BootstrapError")


def test_bootstrap_includes_windows_chrome_candidates(monkeypatch, tmp_path):
    bootstrap = load_bootstrap()
    chrome = tmp_path / "Google" / "Chrome" / "Application" / "chrome.exe"
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path))
    monkeypatch.delenv("PROGRAMFILES(X86)", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    assert chrome in bootstrap._candidate_chrome_paths()


def test_bootstrap_windows_script_installs_system_dependencies_silently():
    script_path = (
        Path(__file__).resolve().parents[1]
        / "skills"
        / "xhs-note-collector"
        / "scripts"
        / "bootstrap_windows.ps1"
    )
    text = script_path.read_text(encoding="utf-8")

    assert "Python.Python.3.12" in text
    assert "OpenJS.NodeJS.LTS" in text
    assert "Google.Chrome" in text
    assert "--silent" in text
    assert "--accept-package-agreements" in text
    assert "--accept-source-agreements" in text
    assert "launch_wizard.py" in text


def test_bootstrap_unix_script_installs_system_dependencies():
    script_path = (
        Path(__file__).resolve().parents[1]
        / "skills"
        / "xhs-note-collector"
        / "scripts"
        / "bootstrap_unix.sh"
    )
    text = script_path.read_text(encoding="utf-8")

    assert "brew install python@3.12" in text
    assert "apt-get install -y python3 python3-pip" in text
    assert "dnf install -y python3 python3-pip" in text
    assert "pacman -Sy --noconfirm python python-pip" in text
    assert "launch_wizard.py" in text
    assert "--max-search-candidates" in text


def test_python_bootstrap_uses_winget_for_windows_system_dependencies(monkeypatch, tmp_path):
    bootstrap = load_bootstrap()
    calls = []
    monkeypatch.setattr(bootstrap, "_is_windows", lambda: True)
    monkeypatch.setattr(bootstrap, "_winget", lambda: "winget")
    monkeypatch.setattr(bootstrap, "_run", lambda cmd, cwd: calls.append((cmd, cwd)))

    bootstrap._run_winget_install(bootstrap.NODE_WINGET_ID, cwd=tmp_path)

    cmd, cwd = calls[0]
    assert cwd == tmp_path
    assert cmd[:4] == ["winget", "install", "--id", "OpenJS.NodeJS.LTS"]
    assert "--exact" in cmd
    assert "--silent" in cmd
    assert "--accept-package-agreements" in cmd


def test_python_bootstrap_installs_node_on_macos(monkeypatch, tmp_path):
    bootstrap = load_bootstrap()
    calls = []

    monkeypatch.setattr(bootstrap, "_is_windows", lambda: False)
    monkeypatch.setattr(bootstrap, "_is_macos", lambda: True)
    monkeypatch.setattr(bootstrap, "_is_linux", lambda: False)
    monkeypatch.setattr(bootstrap, "_ensure_brew", lambda repo: "brew")
    monkeypatch.setattr(bootstrap.shutil, "which", lambda name: None)
    monkeypatch.setattr(bootstrap, "_run", lambda cmd, cwd: calls.append((cmd, cwd)))

    try:
        bootstrap._check_node(tmp_path)
    except bootstrap.BootstrapError:
        pass

    assert (["brew", "install", "node"], tmp_path) in calls


def test_python_bootstrap_installs_chrome_on_macos(monkeypatch, tmp_path):
    bootstrap = load_bootstrap()
    calls = []

    monkeypatch.setattr(bootstrap, "_is_windows", lambda: False)
    monkeypatch.setattr(bootstrap, "_is_macos", lambda: True)
    monkeypatch.setattr(bootstrap, "_is_linux", lambda: False)
    monkeypatch.setattr(bootstrap, "_ensure_brew", lambda repo: "brew")
    monkeypatch.setattr(bootstrap, "find_chrome_executable", lambda: None)
    monkeypatch.setattr(bootstrap, "_run", lambda cmd, cwd: calls.append((cmd, cwd)))

    try:
        bootstrap._check_chrome(tmp_path)
    except bootstrap.BootstrapError:
        pass

    assert (["brew", "install", "--cask", "google-chrome"], tmp_path) in calls
