# --- Imports ---
import streamlit as st
import openai
import json
import pandas as pd
import re
import fitz  # PyMuPDF

# --- OpenAI Setup ---
api_key = st.secrets["OPENAI_API_KEY"]
client = openai.OpenAI(api_key=api_key)

# --- Section Checklists ---
dpdpa_checklists = {
    "4": {
        "title": "Grounds for Processing Personal Data",
        "items": [
            "Personal data is processed only for a lawful purpose.",
            "Lawful purpose means a purpose not expressly forbidden by law.",
            "Lawful purpose must be backed by explicit consent from the Data Principal or fall under legitimate uses."
        ]
    },
    # Add similar checklist dicts for sections 5–8
}

# --- Block Splitter ---
def break_into_blocks(text):
    lines = text.splitlines()
    blocks, current_block = [], []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r'^([A-Z][A-Za-z\s]+|[0-9]+\.\s.*)$', stripped):
            if current_block:
                blocks.append(' '.join(current_block).strip())
                current_block = []
            current_block.append(stripped)
        else:
            current_block.append(stripped)
    if current_block:
        blocks.append(' '.join(current_block).strip())
    return blocks

# --- PDF Extractor ---
def extract_text_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    return "\n".join(page.get_text() for page in doc)

# --- Prompt Generator ---
def create_block_prompt(section_id, block_text, checklist):
    checklist_text = "\n".join(f"- {item}" for item in checklist)
    return f"""
You are a compliance analyst evaluating whether the following privacy policy block meets DPDPA Section {section_id}: {dpdpa_checklists[section_id]['title']}.

**Checklist:**
{checklist_text}

**Policy Block:**
{block_text}

Evaluate each checklist item as: Explicitly Mentioned / Partially Mentioned / Missing.
Return output in this format:
{{
  "Match Level": "...",
  "Compliance Score": 0.0,
  "Checklist Evaluation": [
    {{"Checklist Item": "...", "Status": "...", "Justification": "..."}}
  ],
  "Suggested Rewrite": "...",
  "Simplified Legal Meaning": "..."
}}
"""

# --- GPT Call ---
def call_gpt(prompt):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return json.loads(response.choices[0].message.content)

# --- Scoring Logic ---
def compute_score_and_level(evaluations, total_items):
    matched = [e for e in evaluations if e["Status"].lower() == "explicitly mentioned"]
    partial = [e for e in evaluations if e["Status"].lower() == "partially mentioned"]
    score = (len(matched) + 0.5 * len(partial)) / total_items if total_items else 0.0
    if score >= 1.0:
        level = "Fully Compliant"
    elif score == 0:
        level = "Non-Compliant"
    else:
        level = "Partially Compliant"
    return round(score, 2), level

# --- Analyzer ---
def analyze_policy_section(section_id, checklist, policy_text):
    blocks = break_into_blocks(policy_text)
    all_results = []

    for block in blocks:
        prompt = create_block_prompt(section_id, block, checklist)
        try:
            result = call_gpt(prompt)
            result["Block"] = block
            all_results.append(result)
        except:
            continue

    matched_items = {}
    for res in all_results:
        for item in res.get("Checklist Evaluation", []):
            key = item["Checklist Item"].strip().lower().rstrip('.')
            if key not in matched_items:
                matched_items[key] = item

    evaluations = list(matched_items.values())
    score, level = compute_score_and_level(evaluations, len(checklist))

    return {
        "Section": section_id,
        "Title": dpdpa_checklists[section_id]['title'],
        "Match Level": level,
        "Compliance Score": score,
        "Checklist Items Matched": [item["Checklist Item"] for item in evaluations],
        "Matched Details": evaluations,
        "Suggested Rewrite": all_results[0].get("Suggested Rewrite", ""),
        "Simplified Legal Meaning": all_results[0].get("Simplified Legal Meaning", "")
    }

# --- Streamlit UI ---
st.title("DPDPA Compliance Checker")

upload_option = st.radio("Input method:", ["Paste text", "Upload PDF"])
if upload_option == "Paste text":
    policy_text = st.text_area("Paste your Privacy Policy text:", height=300)
elif upload_option == "Upload PDF":
    uploaded_pdf = st.file_uploader("Upload PDF file", type="pdf")
    if uploaded_pdf:
        policy_text = extract_text_from_pdf(uploaded_pdf)
    else:
        policy_text = ""

section_id = st.selectbox("Choose DPDPA Section", options=list(dpdpa_checklists.keys()))

if st.button("Run Compliance Check") and policy_text:
    checklist = dpdpa_checklists[section_id]['items']
    result = analyze_policy_section(section_id, checklist, policy_text)
    st.json(result)
