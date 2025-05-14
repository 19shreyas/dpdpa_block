# --- Imports ---
import streamlit as st
import openai
import json
import pandas as pd
import re

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

# --- Prompt Generator ---
def create_block_prompt(section_id, block_text, checklist):
    checklist_text = "\n".join(f"- {item}" for item in checklist)
    return f"""
You are a compliance analyst evaluating whether the following privacy policy block meets DPDPA Section {section_id}: {dpdpa_checklists[section_id]['title']}.

**Checklist:**
{checklist_text}

**Policy Block:**
"""
{block_text}
"""

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
            if item["Checklist Item"] not in matched_items:
                matched_items[item["Checklist Item"]] = item

    matched_count = len(matched_items)
    total_items = len(checklist)
    score = matched_count / total_items if total_items else 0
    if matched_count == total_items:
        match_level = "Fully Compliant"
    elif matched_count == 0:
        match_level = "Non-Compliant"
    else:
        match_level = "Partially Compliant"

    return {
        "Section": section_id,
        "Title": dpdpa_checklists[section_id]['title'],
        "Match Level": match_level,
        "Compliance Score": score,
        "Checklist Items Matched": list(matched_items.keys()),
        "Matched Details": list(matched_items.values()),
        "Suggested Rewrite": all_results[0].get("Suggested Rewrite", ""),
        "Simplified Legal Meaning": all_results[0].get("Simplified Legal Meaning", "")
    }

# --- Streamlit UI (minimal for demo) ---
st.title("DPDPA Compliance Checker")

policy_text = st.text_area("Paste your Privacy Policy text:", height=300)
section_id = st.selectbox("Choose DPDPA Section", options=list(dpdpa_checklists.keys()))

if st.button("Run Compliance Check") and policy_text:
    checklist = dpdpa_checklists[section_id]['items']
    result = analyze_policy_section(section_id, checklist, policy_text)
    st.json(result) # Display the structured GPT output
