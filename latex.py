import streamlit as st
import pandas as pd
import re
import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials

load_dotenv()  # Load .env

firebase_config = {
    "type": os.getenv("FIREBASE_TYPE"),
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace('\\n', '\n'),
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
    "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL")
}

if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_config)
    firebase_admin.initialize_app(cred)

db = firestore.client()




# --- Firebase Init ---
if not firebase_admin._apps:
    cred = credentials.Certificate("latex.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- Clear form early if flagged ---
if st.session_state.get("clear_form_flag", False):
    for key in list(st.session_state.keys()):
        if key.startswith("latex_") or key.startswith("ans_") or key == "Question":
            st.session_state[key] = ""
    st.session_state["clear_form_flag"] = False  # Reset the flag

# --- Helpers ---
def extract_dollar_sections(text):
    dollar_sections = re.findall(r'(\$.*?\$)', text)
    modified = text
    latex_map = {}
    for i, section in enumerate(dollar_sections, 1):
        placeholder = f"F{i}"
        modified = modified.replace(section, placeholder, 1)
        latex_map[placeholder] = section[1:-1]
    return latex_map, modified

def replace_placeholders(modified, latex_map):
    for key, val in latex_map.items():
        modified = modified.replace(key, f"${val}$")
    return modified

# --- UI ---
st.title("📘 LaTeX Question Editor")

# Question input
question_input = st.text_input("Question", key="Question")

# Extract LaTeX sections from the question
latex_map, modified_text = extract_dollar_sections(question_input)
st.write(modified_text)

# LaTeX editing section
edited_latex_map = {}
for ph in latex_map:
    val = st.text_input(f"{ph}:", value=latex_map[ph], key=f"latex_{ph}")
    edited_latex_map[ph] = val
    st.latex(val)

# Answer Options
col1, col2, col3, col4 = st.columns(4)
answer_inputs = {}
for col, label in zip([col1, col2, col3, col4], ["A", "B", "C", "D"]):
    with col:
        val = st.text_input(label, key=f"ans_{label}")
        answer_inputs[label] = val
        exps = re.findall(r'\$(.*?)\$', val)
        if exps:
            for e in exps:
                st.latex(e)
        else:
            st.write(val)

# Final reconstructed question
final_q = replace_placeholders(modified_text, edited_latex_map)
st.write(final_q)
st.latex(final_q)
st.write("")

# --- Handlers ---
@firestore.transactional
def add_with_auto_id(transaction, question, answers):
    counter_ref = db.collection("counters").document("questions")
    counter_doc = counter_ref.get(transaction=transaction)
    current_id = counter_doc.get("current") if counter_doc.exists else 0
    new_id = current_id + 1
    transaction.set(counter_ref, {"current": new_id})
    q_ref = db.collection("questions").document(str(new_id))
    transaction.set(q_ref, {
        "id": new_id,
        "Question": question,
        "A": answers["A"],
        "B": answers["B"],
        "C": answers["C"],
        "D": answers["D"]
    })
    return new_id

# --- Buttons ---
colA, colB = st.columns(2)
with colA:
    submitted = st.button("📤 Send to Firebase")
with colB:
    st.button("🔄 Reset Form", on_click=lambda: st.session_state.update({"clear_form_flag": True}))

# --- Submission logic ---
if submitted:
    # Validation for required fields
    if not question_input.strip():
        st.warning("⚠️ Question cannot be empty.")
    elif any(not answer.strip() for answer in answer_inputs.values()):
        st.warning("⚠️ All answers (A, B, C, D) must be filled out.")
    else:
        try:
            transaction = db.transaction()
            new_id = add_with_auto_id(transaction, final_q, answer_inputs)
            st.session_state["clear_form_flag"] = True  # Will trigger clear on next run
            st.success(f"✅ Question saved with ID: {new_id}")
        except Exception as e:
            st.error(f"❌ Failed to send question: {e}")

# --- View All Questions ---
st.subheader("📋 All Questions in Firestore")
try:
    docs = db.collection("questions").stream()
    rows = [{"ID": doc.id, **doc.to_dict()} for doc in docs]
    if rows:
        df = pd.DataFrame(rows)
        st.data_editor(df, use_container_width=True, num_rows="dynamic")
    else:
        st.info("No questions found in Firestore.")
except Exception as e:
    st.error(f"Failed to load questions: {e}")
