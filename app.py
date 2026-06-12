# import json
# import os
# import re
# import threading
# from pathlib import Path
# from typing import List

# from flask import Flask, render_template
# from flask_socketio import SocketIO, emit

# # fuzzy matching
# from rapidfuzz import fuzz, process

# # embeddings
# from sentence_transformers import SentenceTransformer, util

# # Try to import spaCy; if not available we'll fallback to a simple extractor
# try:
#     import spacy
#     NLP = spacy.load("en_core_web_sm")
#     SPACY_AVAILABLE = True
# except Exception:
#     NLP = None
#     SPACY_AVAILABLE = False

# # ---------- Config ----------
# APP_DIR = Path(__file__).parent
# DATA_PATH = APP_DIR / "data.json"
# EMB_CACHE = APP_DIR / "project_embeddings.pt"  # optional cache not used as file, just placeholder
# EMB_MODEL_NAME = "all-MiniLM-L6-v2"  # compact semantic model

# # ---------- Flask setup ----------
# app = Flask(__name__)
# app.config["SECRET_KEY"] = "your_secret_key"
# socketio = SocketIO(app, cors_allowed_origins="*")

# # ---------- Load data ----------
# if not DATA_PATH.exists():
#     raise FileNotFoundError(f"data.json not found at {DATA_PATH.resolve()}")

# with open(DATA_PATH, "r", encoding="utf-8") as f:
#     KB = json.load(f)

# COMPONENTS = [c["name"] for c in KB.get("components", [])]
# COMPONENTS_LOWER = [c.lower() for c in COMPONENTS]
# COMPONENT_REL = {k.lower(): [s.lower() for s in v] for k, v in KB.get("component_relations", {}).items()}

# PROJECTS = KB.get("projects", [])

# # ---------- Load embedding model (this can take a moment) ----------
# print("Loading embedding model:", EMB_MODEL_NAME)
# EMB_MODEL = SentenceTransformer(EMB_MODEL_NAME)
# print("Embedding model loaded.")

# # Precompute project embeddings (combine required components + description)
# project_texts = []
# for p in PROJECTS:
#     parts = []
#     # include required components and optional and description to give richer context
#     parts.extend(p.get("required_components", []))
#     parts.extend(p.get("optional_components", []))
#     parts.append(p.get("description", ""))
#     project_texts.append(" | ".join(parts))

# project_embeddings = EMB_MODEL.encode(project_texts, convert_to_tensor=True)

# # ---------- Utilities ----------

# def fuzzy_match_component(user_input: str, known_components: List[str], threshold: int = 70):
#     """Return best fuzzy match (lowercase) or None."""
#     if not user_input:
#         return None
#     match = process.extractOne(user_input, known_components, scorer=fuzz.partial_ratio)
#     if match and match[1] >= threshold:
#         return match[0]
#     return None

# def expand_components(user_components: List[str]) -> List[str]:
#     """Expand components using component_relations (synonyms) and fuzzy-match them to canonical names."""
#     expanded = set()
#     # normalize input to lowercase strings
#     for comp in user_components:
#         if not comp:
#             continue
#         comp_l = comp.strip().lower()

#         # 1) direct canonical match
#         if comp_l in COMPONENTS_LOWER:
#             idx = COMPONENTS_LOWER.index(comp_l)
#             expanded.add(COMPONENTS[idx].lower())
#             # add relations if any
#             expanded.update(COMPONENT_REL.get(comp_l, []))
#             continue

#         # 2) check if the comp appears as relation key
#         if comp_l in COMPONENT_REL:
#             expanded.update(COMPONENT_REL[comp_l])
#             continue

#         # 3) fuzzy match against canonical components
#         m = fuzzy_match_component(comp_l, COMPONENTS_LOWER, threshold=65)
#         if m:
#             expanded.add(m)
#             expanded.update(COMPONENT_REL.get(m, []))
#             continue

#         # 4) fuzzy match against relation values (e.g., 'esp32' -> 'wifi module')
#         # iterate relations and their synonyms
#         found_alias = None
#         for head, aliases in COMPONENT_REL.items():
#             if comp_l in aliases:
#                 found_alias = head
#                 break
#             # fuzzy check against aliases
#             fm = fuzzy_match_component(comp_l, aliases, threshold=80)
#             if fm:
#                 found_alias = head
#                 break
#         if found_alias:
#             expanded.add(found_alias)
#             expanded.update(COMPONENT_REL.get(found_alias, []))
#             continue

#         # 5) if nothing matches, keep raw (so later embeddings can still pick it up)
#         expanded.add(comp_l)

#     # Map any expanded items back to canonical where possible
#     mapped = set()
#     for item in expanded:
#         if item in COMPONENTS_LOWER:
#             mapped.add(item)
#         else:
#             # try fuzzy map again to canonical names
#             m = fuzzy_match_component(item, COMPONENTS_LOWER, threshold=75)
#             if m:
#                 mapped.add(m)
#             else:
#                 mapped.add(item)
#     return list(mapped)

# # Natural language extraction
# def extract_components_from_text_spacy(user_text: str) -> List[str]:
#     """Use spaCy to extract noun chunks and token candidates, then fuzzy-match them."""
#     if not SPACY_AVAILABLE:
#         return []
#     doc = NLP(user_text.lower())
#     candidates = set()

#     # noun chunks and named entities
#     for chunk in doc.noun_chunks:
#         candidates.add(chunk.text.strip())
#     for ent in doc.ents:
#         candidates.add(ent.text.strip())

#     # also tokens excluding stopwords/punct
#     for tok in doc:
#         if tok.is_stop or tok.is_punct or len(tok.text.strip()) <= 1:
#             continue
#         candidates.add(tok.lemma_.strip())

#     # fuzzy match candidates against known component names and known relation keys/values
#     found = []
#     known = COMPONENTS_LOWER + list(COMPONENT_REL.keys())
#     for cand in candidates:
#         cand_l = cand.lower()
#         m = fuzzy_match_component(cand_l, known, threshold=70)
#         if m:
#             found.append(m)
#     # map found to canonical component names (if m is a relation key, map to canonical)
#     canonical = []
#     for f in found:
#         if f in COMPONENTS_LOWER:
#             canonical.append(f)
#         elif f in COMPONENT_REL:
#             canonical.append(f)
#         else:
#             # final attempt: fuzzy to canonical
#             m2 = fuzzy_match_component(f, COMPONENTS_LOWER, threshold=70)
#             if m2:
#                 canonical.append(m2)
#     return list(set(canonical))

# def extract_components_from_text_fallback(user_text: str) -> List[str]:
#     """Simple regex/token-based extractor for environments without spaCy."""
#     tokens = re.findall(r"[A-Za-z0-9\-+#]+", user_text.lower())
#     candidates = set()
#     # also form bigrams/trigrams for phrases like 'ultrasonic sensor'
#     for i in range(len(tokens)):
#         candidates.add(tokens[i])
#         if i + 1 < len(tokens):
#             candidates.add(tokens[i] + " " + tokens[i + 1])
#         if i + 2 < len(tokens):
#             candidates.add(tokens[i] + " " + tokens[i + 1] + " " + tokens[i + 2])

#     # fuzzy match candidates
#     found = []
#     known = COMPONENTS_LOWER + list(COMPONENT_REL.keys())
#     for cand in candidates:
#         m = fuzzy_match_component(cand, known, threshold=75)
#         if m:
#             found.append(m)
#     return list(set(found))

# def extract_components(user_text: str) -> List[str]:
#     """Unified extractor: spaCy if available else fallback."""
#     if not user_text:
#         return []
#     if SPACY_AVAILABLE:
#         parsed = extract_components_from_text_spacy(user_text)
#         if parsed:
#             return parsed
#     return extract_components_from_text_fallback(user_text)

# # ---------- Matching & scoring ----------
# def find_projects(user_components_raw: List[str]):
#     """Return ranked projects with combined logic score + embedding similarity score."""

#     # 1. normalize & expand
#     expanded = expand_components(user_components_raw)  # returns lowercased names where possible
#     # create a set of canonical lowercased names for logical matching
#     user_set = set(expanded)

#     results = []
#     # for each project compute:
#     #  - logical match fraction = matched_required / total_required
#     #  - embedding similarity = cosine(user_emb, project_emb)
#     #  - combined_score = alpha * logical_frac + (1-alpha) * emb_score_norm
#     # We'll compute user embedding as well from the expanded text

#     # create user text for embedding (join expanded canonical names)
#     user_text = " ".join(expanded)
#     user_emb = EMB_MODEL.encode(user_text, convert_to_tensor=True)

#     # compute embedding similarities
#     sims = util.cos_sim(user_emb, project_embeddings)  # tensor [1, n_projects]

#     for idx, project in enumerate(PROJECTS):
#         required = [r.lower() for r in project.get("required_components", [])]
#         optional = [o.lower() for o in project.get("optional_components", [])]
#         # logical match
#         matched = set(required) & user_set
#         logical_frac = len(matched) / max(1, len(required))

#         # embedding similarity (float)
#         emb_score = float(sims[0, idx].item())  # in [-1,1], typically >0 for related items

#         # normalize emb_score to [0,1] (simple linear transform)
#         emb_score_norm = (emb_score + 1.0) / 2.0

#         # combined: weight logical matching more (alpha)
#         alpha = 0.65
#         combined = alpha * logical_frac + (1 - alpha) * emb_score_norm

#         missing = [r for r in required if r not in user_set]
#         extras = project.get("optional_components", [])

#         results.append({
#             "name": project["name"],
#             "description": project.get("description", ""),
#             "logical_frac": round(logical_frac, 3),
#             "emb_score": round(emb_score, 3),
#             "combined_score": round(combined, 3),
#             "missing": missing,
#             "extras": extras,
#             "matched": list(matched)
#         })

#     # sort by combined_score desc
#     results.sort(key=lambda x: x["combined_score"], reverse=True)
#     return expanded, results

# # ---------- Flask endpoints ----------
# @app.route("/")
# def index():
#     # pass canonical components with descriptions to template
#     return render_template("index.html", components=KB.get("components", []))

# @socketio.on("send_message")
# def handle_message(payload):
#     """
#     payload = { "message": <string or list> }
#     """
#     user_input = payload.get("message", "")
#     # if list (from checkboxes) use as components; if string, try to extract
#     if isinstance(user_input, list):
#         user_components = user_input
#     else:
#         # try to parse comma separated first (fast path)
#         text = str(user_input).strip()
#         if "," in text and len(text) < 200:
#             # assume user gave a simple comma list like "Arduino, LED, Motor"
#             user_components = [t.strip() for t in text.split(",") if t.strip()]
#         else:
#             # otherwise extract from natural language
#             user_components = extract_components(text)
#             # if extractor failed to return anything, also attempt a quick token split
#             if not user_components:
#                 user_components = [tok.strip() for tok in re.split(r"[ ,;]+", text) if tok.strip()]

#     if not user_components:
#         emit("receive_message", {"message": "I couldn't recognize any components. Try naming hardware parts like 'Arduino, LED, Motor'."})
#         return

#     expanded, projects = find_projects(user_components)

#     # Build a friendly response
#     if not projects:
#         emit("receive_message", {"message": "No project matches found."})
#         return

#     # present top 6 hits
#     top = projects[:6]
#     response_lines = []
#     response_lines.append(f"Based on your components ({', '.join(user_components)}). Expanded to: {', '.join(expanded)}\n")
#     for p in top:
#         pct = int(p["combined_score"] * 100)
#         response_lines.append(f"🔹 {p['name']} ({pct}% match)")
#         response_lines.append(f"   • {p['description']}")
#         if p["matched"]:
#             response_lines.append(f"   • Matched components: {', '.join(p['matched'])}")
#         if p["missing"]:
#             response_lines.append(f"   • Missing: {', '.join(p['missing'])}")
#         if p["extras"]:
#             response_lines.append(f"   • Enhancements: {', '.join(p['extras'])}")
#         response_lines.append(f"   • (logical={p['logical_frac']}, emb={p['emb_score']})\n")

#     emit("receive_message", {"message": "\n".join(response_lines)})

# # ---------- Run ----------
# if __name__ == "__main__":
#     # For dev: socketio.run(app, debug=True) but use host=0.0.0.0 if you want external access
#     socketio.run(app, host="127.0.0.1", port=5000, debug=True)

import json
import os
import re
from pathlib import Path
from typing import List
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from rapidfuzz import fuzz, process
from sentence_transformers import SentenceTransformer, util

try:
    import spacy
    NLP = spacy.load("en_core_web_sm")
    SPACY_AVAILABLE = True
except Exception:
    NLP = None
    SPACY_AVAILABLE = False

# ---------- Config ----------
APP_DIR = Path(__file__).parent
DATA_PATH = APP_DIR / "data.json"
FEEDBACK_PATH = APP_DIR / "feedback.json"
EMB_MODEL_NAME = "all-MiniLM-L6-v2"

# ---------- Flask setup ----------
app = Flask(__name__)
app.config["SECRET_KEY"] = "bda8bf66a778706abe6d7f18d3195ec87ca0702cf352592c66365ce8ccc3980f"
socketio = SocketIO(app, cors_allowed_origins="*")

# ---------- Load Data ----------
if not DATA_PATH.exists():
    raise FileNotFoundError(f"data.json not found at {DATA_PATH.resolve()}")

with open(DATA_PATH, "r", encoding="utf-8") as f:
    KB = json.load(f)

COMPONENTS = [c["name"] for c in KB.get("components", [])]
COMPONENTS_LOWER = [c.lower() for c in COMPONENTS]
COMPONENT_REL = {k.lower(): [s.lower() for s in v] for k, v in KB.get("component_relations", {}).items()}
PROJECTS = KB.get("projects", [])

# Load or create feedback file
if not FEEDBACK_PATH.exists():
    with open(FEEDBACK_PATH, "w") as f:
        json.dump({}, f)

with open(FEEDBACK_PATH, "r") as f:
    FEEDBACK = json.load(f)

# ---------- Embedding Model ----------
print("Loading embedding model:", EMB_MODEL_NAME)
EMB_MODEL = SentenceTransformer(EMB_MODEL_NAME)
print("Embedding model loaded.")

project_texts = []
for p in PROJECTS:
    parts = []
    parts.extend(p.get("required_components", []))
    parts.extend(p.get("optional_components", []))
    parts.append(p.get("description", ""))
    project_texts.append(" | ".join(parts))
project_embeddings = EMB_MODEL.encode(project_texts, convert_to_tensor=True)

# ---------- Utilities ----------
def fuzzy_match_component(user_input: str, known_components: List[str], threshold: int = 70):
    if not user_input:
        return None
    match = process.extractOne(user_input, known_components, scorer=fuzz.partial_ratio)
    if match and match[1] >= threshold:
        return match[0]
    return None

def expand_components(user_components: List[str]) -> List[str]:
    expanded = set()
    for comp in user_components:
        if not comp:
            continue
        comp_l = comp.strip().lower()
        if comp_l in COMPONENTS_LOWER:
            idx = COMPONENTS_LOWER.index(comp_l)
            expanded.add(COMPONENTS[idx].lower())
            expanded.update(COMPONENT_REL.get(comp_l, []))
            continue
        if comp_l in COMPONENT_REL:
            expanded.update(COMPONENT_REL[comp_l])
            continue
        m = fuzzy_match_component(comp_l, COMPONENTS_LOWER, threshold=65)
        if m:
            expanded.add(m)
            expanded.update(COMPONENT_REL.get(m, []))
            continue
        found_alias = None
        for head, aliases in COMPONENT_REL.items():
            if comp_l in aliases:
                found_alias = head
                break
            fm = fuzzy_match_component(comp_l, aliases, threshold=80)
            if fm:
                found_alias = head
                break
        if found_alias:
            expanded.add(found_alias)
            expanded.update(COMPONENT_REL.get(found_alias, []))
            continue
        expanded.add(comp_l)
    mapped = set()
    for item in expanded:
        if item in COMPONENTS_LOWER:
            mapped.add(item)
        else:
            m = fuzzy_match_component(item, COMPONENTS_LOWER, threshold=75)
            mapped.add(m if m else item)
    return list(mapped)

def extract_components_from_text_fallback(user_text: str) -> List[str]:
    tokens = re.findall(r"[A-Za-z0-9\-+#]+", user_text.lower())
    candidates = set()
    for i in range(len(tokens)):
        candidates.add(tokens[i])
        if i + 1 < len(tokens):
            candidates.add(tokens[i] + " " + tokens[i + 1])
        if i + 2 < len(tokens):
            candidates.add(tokens[i] + " " + tokens[i + 1] + " " + tokens[i + 2])
    found = []
    known = COMPONENTS_LOWER + list(COMPONENT_REL.keys())
    for cand in candidates:
        m = fuzzy_match_component(cand, known, threshold=75)
        if m:
            found.append(m)
    return list(set(found))

def extract_components(user_text: str) -> List[str]:
    if not user_text:
        return []
    if SPACY_AVAILABLE:
        doc = NLP(user_text.lower())
        candidates = {chunk.text.strip() for chunk in doc.noun_chunks}
        candidates.update({tok.lemma_.strip() for tok in doc if not tok.is_stop and not tok.is_punct})
        found = []
        known = COMPONENTS_LOWER + list(COMPONENT_REL.keys())
        for cand in candidates:
            m = fuzzy_match_component(cand, known, threshold=70)
            if m:
                found.append(m)
        return list(set(found))
    return extract_components_from_text_fallback(user_text)

# ---------- Matching ----------
def find_projects(user_components_raw: List[str]):
    expanded = expand_components(user_components_raw)
    user_set = set(expanded)
    user_text = " ".join(expanded)
    user_emb = EMB_MODEL.encode(user_text, convert_to_tensor=True)
    sims = util.cos_sim(user_emb, project_embeddings)
    results = []
    for idx, project in enumerate(PROJECTS):
        required = [r.lower() for r in project.get("required_components", [])]
        matched = set(required) & user_set
        logical_frac = len(matched) / max(1, len(required))
        emb_score = float(sims[0, idx].item())
        emb_score_norm = (emb_score + 1.0) / 2.0
        alpha = 0.65
        combined = alpha * logical_frac + (1 - alpha) * emb_score_norm

        # Feedback boost
        likes = FEEDBACK.get(project["name"], {}).get("likes", 0)
        dislikes = FEEDBACK.get(project["name"], {}).get("dislikes", 0)
        feedback_factor = (likes - dislikes) * 0.03  # increased weight
        combined = min(1.0, combined + feedback_factor)

        results.append({
            "name": project["name"],
            "description": project.get("description", ""),
            "combined_score": round(combined, 3),
            "matched": list(matched),
            "missing": [r for r in required if r not in user_set],
            "extras": project.get("optional_components", [])
        })
    results.sort(key=lambda x: x["combined_score"], reverse=True)
    return expanded, results

# ---------- Flask endpoints ----------
@app.route("/")
def index():
    return render_template("index.html", components=KB.get("components", []))

@socketio.on("send_message")
def handle_message(payload):
    user_input = payload.get("message", "")
    text = str(user_input).strip().lower()

    # --- Intent Recognition ---
    # Detect questions like "what are the components needed for ..."
    component_q_pattern = re.search(r"components (?:needed|required|used).*for (.+)", text)
    if component_q_pattern:
        project_name = component_q_pattern.group(1).strip()
        matched_project = None
        highest_ratio = 0
        for p in PROJECTS:
            ratio = fuzz.partial_ratio(project_name, p["name"].lower())
            if ratio > highest_ratio and ratio > 70:
                matched_project = p
                highest_ratio = ratio

        if matched_project:
            required = ", ".join(matched_project.get("required_components", []))
            optional = ", ".join(matched_project.get("optional_components", []))
            description = matched_project.get("description", "")
            response = (
                f"🔹 *{matched_project['name']}*\n"
                f"• Description: {description}\n"
                f"• Required Components: {required if required else 'Not listed'}\n"
                f"• Optional Components: {optional if optional else 'None'}"
            )
            emit("receive_message", {"message": response})
            return
        else:
            emit("receive_message", {"message": f"I couldn’t find a project named '{project_name}'."})
            return

    # --- Regular component-based workflow ---
    if isinstance(user_input, list):
        user_components = user_input
    else:
        if "," in text and len(text) < 200:
            user_components = [t.strip() for t in text.split(",") if t.strip()]
        else:
            user_components = extract_components(text)
            if not user_components:
                user_components = [tok.strip() for tok in re.split(r"[ ,;]+", text) if tok.strip()]

    if not user_components:
        emit("receive_message", {"message": "I couldn't recognize any components."})
        return

    expanded, projects = find_projects(user_components)
    if not projects:
        emit("receive_message", {"message": "No project matches found."})
        return

    top = projects[:6]
    lines = [f"Based on your components ({', '.join(user_components)}):"]
    for p in top:
        pct = int(p["combined_score"] * 100)
        lines.append(f"🔹 {p['name']} ({pct}% match)")
        lines.append(f"   • {p['description']}")
        if p["matched"]:
            lines.append(f"   • Matched: {', '.join(p['matched'])}")
        if p["missing"]:
            lines.append(f"   • Missing: {', '.join(p['missing'])}")
        lines.append(f"   • Enhancements: {', '.join(p['extras'])}")
        lines.append(f"   • Feedback: 👍 {FEEDBACK.get(p['name'], {}).get('likes', 0)} | 👎 {FEEDBACK.get(p['name'], {}).get('dislikes', 0)}")
        lines.append(f"[Send: like {p['name']} | dislike {p['name']}]")
        lines.append("")

    emit("receive_message", {"message": "\n".join(lines)})

@socketio.on("send_feedback")
def handle_feedback(data):
    project = data.get("project")
    sentiment = data.get("sentiment")
    if not project:
        return
    if project not in FEEDBACK:
        FEEDBACK[project] = {"likes": 0, "dislikes": 0}
    if sentiment == "like":
        FEEDBACK[project]["likes"] += 1
    elif sentiment == "dislike":
        FEEDBACK[project]["dislikes"] += 1

    # Save feedback persistently
    with open(FEEDBACK_PATH, "w") as f:
        json.dump(FEEDBACK, f, indent=4)

    emit("receive_message", {"message": f"Feedback recorded for '{project}' ({sentiment}). The system will learn from it."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)