from livekit.agents import function_tool
import os
import json
import subprocess
import openai
import zipfile
import re
import shutil
import tempfile
import difflib
import threading
import time
from dotenv import load_dotenv

# File-watching
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

load_dotenv()

SPRING_BOOT_PATH = os.getenv("SPRING_BOOT_PATH", "~/spring_projects")

SPRING_PROJECTS_ROOT = os.path.expanduser(SPRING_BOOT_PATH)
SPRING_MEMORY_FILE = os.path.join(SPRING_PROJECTS_ROOT, "project_memory.json")

# How many files of context to provide to the model
CONTEXT_FILE_COUNT = 5

def save_current_spring_project(project_path: str):
    os.makedirs(SPRING_PROJECTS_ROOT, exist_ok=True)
    with open(SPRING_MEMORY_FILE, "w") as f:
        json.dump({"current_project": project_path}, f)

def get_current_spring_project() -> str:
    if os.path.exists(SPRING_MEMORY_FILE):
        with open(SPRING_MEMORY_FILE, "r") as f:
            data = json.load(f)
            return data.get("current_project")
    return None

def get_java_comment_prefix(file_name: str) -> str:
    return "//"

def replace_demo_application(project_path: str, project_name: str, package_name: str):
    """
    Rename DemoApplication.java to <ProjectName>Application.java and update class name.
    """
    src_root = os.path.join(project_path, "src", "main", "java")
    package_path = os.path.join(src_root, *package_name.split('.'))
    demo_file = os.path.join(package_path, "DemoApplication.java")
    new_file = os.path.join(package_path, f"{project_name}Application.java")

    if os.path.exists(demo_file):
        with open(demo_file, "r") as f:
            content = f.read()
        content = re.sub(r'public class DemoApplication', f'public class {project_name}Application', content)
        with open(new_file, "w") as f:
            f.write(content)
        os.remove(demo_file)

def write_custom_build_gradle(project_path: str, package_name: str):
    build_gradle_content = f"""plugins {{
    id 'java'
    id 'org.springframework.boot' version '3.4.5'
    id 'io.spring.dependency-management' version '1.1.7'
}}

group = '{package_name}'
version = '0.0.1-SNAPSHOT'

java {{
    toolchain {{
        languageVersion = JavaLanguageVersion.of(17)
    }}
}}

repositories {{
    mavenCentral()
}}

dependencies {{
    implementation 'org.springframework.boot:spring-boot-starter-jdbc'
    implementation 'org.springframework.boot:spring-boot-starter-web'
    implementation 'org.springframework.boot:spring-boot-starter-security'
    implementation 'org.springframework.boot:spring-boot-starter-data-jpa'

    // Proper Lombok dependencies
    compileOnly 'org.projectlombok:lombok:1.18.30'
    annotationProcessor 'org.projectlombok:lombok:1.18.30'
    testCompileOnly 'org.projectlombok:lombok:1.18.30'
    testAnnotationProcessor 'org.projectlombok:lombok:1.18.30'

    testImplementation 'org.springframework.security:spring-security-test'
    developmentOnly 'org.springframework.boot:spring-boot-devtools'
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
    runtimeOnly 'org.postgresql:postgresql'
    testRuntimeOnly 'org.junit.platform:junit-platform-launcher'
    implementation 'io.jsonwebtoken:jjwt-api:0.12.5'
    runtimeOnly 'io.jsonwebtoken:jjwt-impl:0.12.5'
    runtimeOnly 'io.jsonwebtoken:jjwt-jackson:0.12.5'
}}

tasks.named('test') {{
    useJUnitPlatform()
}}
"""
    with open(os.path.join(project_path, "build.gradle"), "w") as f:
        f.write(build_gradle_content)

# -------------------------
# Safe diff & patch helpers
# -------------------------
def compute_unified_diff(old_text: str, new_text: str, fromfile: str = "a", tofile: str = "b"):
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    diff_lines = difflib.unified_diff(old_lines, new_lines, fromfile=fromfile, tofile=tofile)
    return "".join(diff_lines)

def apply_safe_patch(file_path: str, new_text: str) -> bool:
    """
    Attempt to apply only modified line ranges (based on difflib opcodes).
    Returns True on success, False if we fall back to overwrite.
    This function always writes to a temp file then moves it into place to avoid partial writes.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            old_text = f.read()
    except FileNotFoundError:
        # file doesn't exist, just write
        old_text = ""

    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines)
    # Build the resulting lines by taking unchanged slices and replacing changed slices with new content
    result_lines = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            result_lines.extend(old_lines[i1:i2])
        else:
            # for replace/insert/delete take from new_lines
            result_lines.extend(new_lines[j1:j2])

    # Now write to temp and move into place
    try:
        fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(file_path))
        with os.fdopen(fd, "w", encoding="utf-8") as tmpf:
            tmpf.write("".join(result_lines))
        # atomically replace
        os.replace(tmp_path, file_path)
        return True
    except Exception:
        # cleanup
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        return False

def overwrite_with_fallback(file_path: str, new_text: str):
    """
    Overwrite the file, used as fallback if safe patch fails.
    """
    try:
        # write to temp then move
        fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(file_path))
        with os.fdopen(fd, "w", encoding="utf-8") as tmpf:
            tmpf.write(new_text)
        os.replace(tmp_path, file_path)
        return True
    except Exception:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        return False

# -------------------------
# Context helpers
# -------------------------
def list_java_files_sorted_by_mtime(project_path: str):
    java_files = []
    for root, _, files in os.walk(project_path):
        for f in files:
            if f.endswith(".java"):
                java_files.append(os.path.join(root, f))
    java_files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return java_files

def read_last_n_java_files(project_path: str, n: int = CONTEXT_FILE_COUNT) -> dict:
    """
    Returns a dict of filepath -> content for the last n modified java files.
    """
    java_files = list_java_files_sorted_by_mtime(project_path)
    out = {}
    for p in java_files[:n]:
        try:
            with open(p, "r", encoding="utf-8") as f:
                out[p] = f.read()
        except Exception:
            out[p] = "<UNREADABLE>"
    return out

# -------------------------
# File watcher (background)
# -------------------------
class AIFileChangeHandler(PatternMatchingEventHandler):
    def __init__(self, project_path, on_change_cb, patterns=["*.java", "*.gradle", "*.properties", "*.xml", "*.kt"], ignore_patterns=None):
        super().__init__(patterns=patterns, ignore_patterns=ignore_patterns, ignore_directories=True, case_sensitive=False)
        self.project_path = project_path
        self.on_change_cb = on_change_cb
        self._debounce = {}
        self._debounce_delay = 0.5  # seconds

    def _maybe_debounce(self, path):
        now = time.time()
        last = self._debounce.get(path, 0)
        self._debounce[path] = now
        return (now - last) > self._debounce_delay

    def dispatch(self, event):
        # We debounce rapid repeated events
        if not self._maybe_debounce(event.src_path):
            return
        super().dispatch(event)

    def on_modified(self, event):
        # call the callback in a separate thread to avoid blocking watchdog internals
        threading.Thread(target=self.on_change_cb, args=(event.src_path,)).start()

# Keep a global observer so it can be started/stopped
_GLOBAL_WATCHERS = {}

def start_file_watcher_for_project(project_path: str, on_change_cb):
    """
    Start watching project_path for file changes (java/gradle/properties). If already watching, no-op.
    """
    if project_path in _GLOBAL_WATCHERS:
        return

    event_handler = AIFileChangeHandler(project_path, on_change_cb)
    observer = Observer()
    observer.schedule(event_handler, project_path, recursive=True)
    observer.daemon = True
    observer.start()
    _GLOBAL_WATCHERS[project_path] = observer

def stop_file_watcher_for_project(project_path: str):
    obs = _GLOBAL_WATCHERS.pop(project_path, None)
    if obs:
        obs.stop()
        obs.join(timeout=2)

# -------------------------
# AI integration helpers
# -------------------------
def build_context_prompt(project_path: str, changed_file: str = None) -> str:
    """
    Build a prompt that includes the last N Java files and an optional changed-file snippet.
    """
    context_files = read_last_n_java_files(project_path, n=CONTEXT_FILE_COUNT)
    prompt_parts = []
    prompt_parts.append("You are a smart coding assistant. You will receive a file change and should produce a unified diff patch or a short suggestion.\n")
    if changed_file:
        prompt_parts.append(f"Changed file: {changed_file}\n")
        try:
            with open(changed_file, "r", encoding="utf-8") as f:
                prompt_parts.append("Changed file content:\n")
                prompt_parts.append(f.read()[:30_000])  # avoid enormous payloads
        except Exception:
            prompt_parts.append("Changed file content: <UNREADABLE>\n")

    prompt_parts.append("\nRecent project files (paths and contents):\n")
    for p, content in context_files.items():
        prompt_parts.append(f"##### PATH: {p}\n")
        prompt_parts.append(content[:20_000])  # truncate each file
        prompt_parts.append("\n\n")
    prompt_parts.append("\nNow, produce either:\n1) A unified diff (git-style) patch that updates only modified lines (preferred), or\n2) If you cannot produce a safe patch, provide the full corrected file contents and explain why.\n\nReturn only the diff or the full file content block wrapped with markers so the caller can detect which it is.\n")
    return "\n".join(prompt_parts)

def ask_model_for_patch(changed_file: str, project_path: str, user_note: str = "") -> dict:
    """
    Ask the LLM to propose a patch for the changed file. Returns dict:
      {"type":"diff"|"full"|"none", "content": "..."}
    """
    openai.api_key = os.getenv("OPENAI_API_KEY")
    if not openai.api_key:
        return {"type": "none", "content": "OpenAI API key missing."}

    prompt = build_context_prompt(project_path, changed_file)
    if user_note:
        prompt += "\nUser note: " + user_note + "\n"

    # Use chat completions (adjust to your OpenAI client version)
    try:
        response = openai.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are a reliable assistant that outputs unified diffs or full file contents only."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
        )
        text = response.choices[0].message.content.strip()
        # Decide whether it's a diff or full content by simple detection
        if text.startswith("--- ") or text.startswith("diff --git") or "+++" in text:
            return {"type": "diff", "content": text}
        # If they returned a triple-backtick block, strip markers and treat as full
        m = re.search(r"```(?:java|text)?\n([\s\S]*)\n```", text)
        if m:
            return {"type": "full", "content": m.group(1)}
        # He might return raw content - heuristics: many lines and contains class definition
        if "class " in text and ("{" in text or ";" in text):
            return {"type": "full", "content": text}
        return {"type": "none", "content": text}
    except Exception as e:
        return {"type": "none", "content": f"model error: {e}"}

# -------------------------
# On-change callback
# -------------------------
def _on_file_change(changed_path: str):
    """
    Called when a file changes. Will request AI suggestions/patch and try to apply them safely.
    Runs in background thread.
    """
    project_path = get_current_spring_project()
    if not project_path:
        return

    # We only process files inside the current project
    if not os.path.commonpath([project_path, changed_path]).startswith(project_path):
        return

    # Read current file content
    try:
        with open(changed_path, "r", encoding="utf-8") as f:
            new_text = f.read()
    except Exception:
        return

    # Ask model for improvements or fixes
    model_resp = ask_model_for_patch(changed_path, project_path)

    # If model returned a diff, try to apply (we'll convert diff to new content by patching)
    if model_resp["type"] == "diff":
        # Try to apply the unified diff by reconstructing the new file
        try:
            # Get old text
            try:
                with open(changed_path, "r", encoding="utf-8") as f:
                    old_text = f.read()
            except FileNotFoundError:
                old_text = ""

            # Attempt to apply diff using python's difflib by constructing new text:
            # We'll try to use unified_diff to compute a desired new_text for safety check:
            # (We cannot reliably parse arbitrary diffs here, so fallback to sending diff back to user.)
            # For now, we will attempt to ask model for full content if it also included full block fallback.
            # We'll attempt to patch by asking model again for full content if needed.
            # (Applying raw diff reliably requires a full patch tool.)
            # So, attempt to request full content explicitly:
            second = ask_model_for_patch(changed_path, project_path, user_note="Please return full updated file content (no diff) so I can apply it safely.")
            if second["type"] == "full":
                success = apply_safe_patch(changed_path, second["content"])
                if not success:
                    overwrite_with_fallback(changed_path, second["content"])
            else:
                # cannot get full content, abort and log to file
                log_path = os.path.join(project_path, ".ai_patch_failure.log")
                with open(log_path, "a", encoding="utf-8") as logf:
                    logf.write(f"[{time.ctime()}] Could not obtain full content for diff for {changed_path}\nModel diff:\n{model_resp['content']}\n\n")
        except Exception as e:
            # fallback: write model output into a log
            log_path = os.path.join(project_path, ".ai_patch_error.log")
            with open(log_path, "a", encoding="utf-8") as logf:
                logf.write(f"[{time.ctime()}] Error applying diff for {changed_path}: {e}\nResponse:\n{model_resp['content']}\n\n")
        return

    if model_resp["type"] == "full":
        # Try safe patch first
        full_content = model_resp["content"]
        if not apply_safe_patch(changed_path, full_content):
            # fallback overwrite
            overwrite_with_fallback(changed_path, full_content)
        return

    # If none, just store model response for manual inspection
    if model_resp["type"] == "none":
        log_path = os.path.join(project_path, ".ai_patch_info.log")
        with open(log_path, "a", encoding="utf-8") as logf:
            logf.write(f"[{time.ctime()}] AI returned nothing actionable for {changed_path}:\n{model_resp['content']}\n\n")

# -------------------------
# function_tools (exposed)
# -------------------------
@function_tool
async def manage_spring_boot_project(project_name: str, package_name: str = "com.danielscode") -> str:
    """
    Fully mimic Spring Initializr, download project, unzip, set dependencies, rename DemoApplication.
    Also starts a background file watcher for the project so the AI can watch edits in real time.
    """
    try:
        os.makedirs(SPRING_PROJECTS_ROOT, exist_ok=True)
        project_path = os.path.join(SPRING_PROJECTS_ROOT, project_name)
        project_exists = os.path.exists(project_path)

        if not project_exists:
            # Download starter project using start.spring.io (gradle + java 17)
            zip_path = os.path.join(SPRING_PROJECTS_ROOT, f"{project_name}.zip")
            subprocess.run([
                "curl", "-s",
                f"https://start.spring.io/starter.zip?type=gradle-project&language=java&bootVersion=3.4.5&baseDir={project_name}&groupId={package_name}&artifactId={project_name}&name={project_name}&packageName={package_name}&javaVersion=17",
                "-o", zip_path
            ], check=True)

            # Unzip
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(SPRING_PROJECTS_ROOT)
            os.remove(zip_path)

            # Overwrite build.gradle with custom dependencies
            write_custom_build_gradle(project_path, package_name)

            # Rename DemoApplication to <ProjectName>Application
            replace_demo_application(project_path, project_name, package_name)

        save_current_spring_project(project_path)

        # Open in IntelliJ IDEA
        applescript = f'''
        tell application "IntelliJ IDEA"
            open POSIX file "{project_path}"
            activate
        end tell
        '''
        subprocess.run(["osascript", "-e", applescript])

        # Start file watcher in background
        start_file_watcher_for_project(project_path, _on_file_change)

        return f"🆕 Created and opened Spring Boot project: {project_name}" if not project_exists else f"📂 Opened existing Spring Boot project: {project_name}"

    except subprocess.CalledProcessError as e:
        return f"❌ Failed during shell operation: {e}"
    except Exception as e:
        return f"❌ Failed to manage Spring Boot project: {str(e)}"

@function_tool
async def create_or_open_spring_file(file_name: str) -> str:
    """
    Create or open a file inside the active Spring Boot project.
    """
    try:
        project_path = get_current_spring_project()
        if not project_path:
            return "⚠️ No active Spring Boot project found. Use manage_spring_boot_project first."

        file_path = os.path.join(project_path, file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        open(file_path, "a").close()

        applescript = f'''
        tell application "IntelliJ IDEA"
            open POSIX file "{file_path}"
            activate
        end tell
        '''
        subprocess.run(["osascript", "-e", applescript])

        return f"✅ File '{file_name}' opened at {file_path}"

    except Exception as e:
        return f"❌ Failed to open Spring Boot file: {str(e)}"

@function_tool
async def generate_spring_java_code(file_name: str, prompt: str, model: str = "gpt-5-mini") -> str:
    """
    Generate Java code using GPT-5 inside the active Spring Boot project. Uses context (last N java files)
    and writes the result with safer patching (modified-line updates first; fallback overwrite).
    """
    try:
        project_path = get_current_spring_project()
        if not project_path:
            return "⚠️ No active Spring Boot project found. Use manage_spring_boot_project first."

        file_path = os.path.join(project_path, file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        openai.api_key = os.getenv("OPENAI_API_KEY")
        if not openai.api_key:
            return "⚠️ OpenAI API key not set."

        # Build context + user prompt for the model and ask for full file content
        context_prompt = build_context_prompt(project_path, changed_file=file_path)
        final_prompt = context_prompt + "\nUSER REQUEST: " + prompt + "\n\nPlease return the full contents of the requested file (no explanations)."

        response = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert Java developer producing only the file contents requested."},
                {"role": "user", "content": final_prompt}
            ],
            max_tokens=3000,
        )

        text = response.choices[0].message.content.strip()
        # Strip code fences if present
        m = re.search(r"```(?:java)?\n([\s\S]*)\n```", text)
        if m:
            new_content = m.group(1)
        else:
            new_content = text

        # Try safe patch first
        patched = apply_safe_patch(file_path, new_content)
        if not patched:
            overwrite_with_fallback(file_path, new_content)

        # Open file in IntelliJ to show changes
        applescript = f'''
        tell application "IntelliJ IDEA"
            open POSIX file "{file_path}"
            activate
        end tell
        '''
        subprocess.run(["osascript", "-e", applescript])

        return f"✅ Java code generated and written to '{file_name}' (safer-patched)."

    except Exception as e:
        return f"❌ Failed to generate Spring Boot Java code: {str(e)}"