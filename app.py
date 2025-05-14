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
    "5": {
        "title": "Notice",
        "items": [
            "Notice is provided in clear and plain language.",
            "Notice is made available before or at the time of data collection.",
            "Notice includes the purpose of processing personal data.",
            "Notice specifies the rights of the Data Principal.",
            "Notice includes details of the Data Fiduciary and means to contact them.",
            "Notice discloses the manner in which the Data Principal can exercise their rights.",
            "Notice is accessible in English or any language listed in the Eighth Schedule of the Constitution of India."
        ]
    },
    "6": {
        "title": "Consent",
        "items": [
            "Consent is free (voluntary, not coerced).",
            "Consent is specific to a clearly defined purpose.",
            "Consent is informed (based on full information provided beforehand).",
            "Consent is unambiguous (clearly understood and intentional).",
            "Consent is given via clear affirmative action.",
            "Consent is limited to the specified purpose only.",
            "Only personal data necessary for the purpose is processed.",
            "Consent is provided before data processing begins.",
            "Data Principal has the ability to withdraw consent easily and at any time.",
            "If consent is withdrawn, data processing stops and data is erased unless legally required."
        ]
    },
    "7": {
        "title": "Certain Legitimate Uses",
        "items": [
            "Processing is necessary for performance of any function under the law or in the interest of the sovereignty and integrity of India.",
            "Processing is necessary for compliance with any judgment, order, or decree of any court or tribunal in India.",
            "Processing is necessary for responding to a medical emergency involving a threat to life or health.",
            "Processing is necessary for taking measures to ensure safety during any disaster or breakdown of public order.",
            "Processing is necessary for purposes related to employment or provision of service.",
            "Processing is necessary for the purpose of public interest such as prevention of fraud, network and information security, or credit scoring.",
            "Processing is for purposes of corporate governance, mergers, or disclosures under legal obligations.",
            "Processing is necessary for any fair and reasonable purpose specified by the Data Protection Board."
        ]
    },
    "8": {
        "title": "General Obligations of Data Fiduciary",
        "items": [
            "Implements appropriate technical and organizational measures to ensure compliance with DPDPA.",
            "Maintains data accuracy and completeness to ensure it is up-to-date.",
            "Implements reasonable security safeguards to prevent personal data breaches.",
            "Notifies the Data Protection Board and affected Data Principals in the event of a breach.",
            "Erases personal data as soon as the purpose is fulfilled and retention is no longer necessary.",
            "Maintains records of processing activities in accordance with prescribed rules.",
            "Conducts periodic Data Protection Impact Assessments if required.",
            "Appoints a Data Protection Officer (DPO) if classified as a Significant Data Fiduciary.",
            "Publishes the business contact information of the DPO or person handling grievances."
        ]
    }
    }
    # Add similar checklist dicts for sections 5–8

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

    if section_id == "8":
        canonical_display_map = {
            "implements appropriate technical and organizational measures": "Implements appropriate technical and organizational measures to ensure compliance with DPDPA.",
            "maintains data accuracy and completeness": "Maintains data accuracy and completeness to ensure it is up-to-date.",
            "implements reasonable security safeguards": "Implements reasonable security safeguards to prevent personal data breaches.",
            "notifies the data protection board and affected data principals in case of breach": "Notifies the Data Protection Board and affected Data Principals in the event of a breach.",
            "erases personal data when purpose is fulfilled": "Erases personal data as soon as the purpose is fulfilled and retention is no longer necessary.",
            "maintains records of processing activities": "Maintains records of processing activities in accordance with prescribed rules.",
            "conducts data protection impact assessments": "Conducts periodic Data Protection Impact Assessments if required.",
            "appoints a data protection officer": "Appoints a Data Protection Officer (DPO) if classified as a Significant Data Fiduciary.",
            "publishes dpo contact information": "Publishes the business contact information of the DPO or person handling grievances."
        }
    else:
        canonical_display_map = {}

    for res in all_results:
        for item in res.get("Checklist Evaluation", []):
            key = item["Checklist Item"].strip().lower().replace(".", "")

            if section_id == "8":
                for match in canonical_display_map.keys():
                    if match in key:
                        key = match
                        break

            if "all other checklist items" in key:
                continue

            if key not in matched_items:
                item["Checklist Item"] = canonical_display_map.get(key, item["Checklist Item"])
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

