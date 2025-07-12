import requests
import json
import os

# --------------- CONFIG ---------------
API_KEY = "MI0QanRHLm4ovFkBVqcBrx3LCiWLT8eu"
EMAIL = " test@heidihealth.com"
USER_UID = "123"
BASE_URL = "https://registrar.api.heidihealth.com/api/v2/ml-scribe/open-api"
TEMPLATE_ID = "659b8042fe093d6592b41ef7"

def stream_response_to_text(response):
    full_text = ""
    for chunk in response.iter_lines():
        if chunk:
            decoded = chunk.decode('utf-8').strip()
            if decoded.startswith("data:"):
                decoded = decoded[len("data:"):].strip()
            try:
                data_json = json.loads(decoded)
                full_text += data_json.get("data", "")
            except json.JSONDecodeError:
                full_text += decoded
    return full_text


# --------------- HEADERS ---------------
def auth_headers(token=None):
    return {"Heidi-Api-Key": API_KEY} if not token else {"Authorization": f"Bearer {token}"}

# --------------- STEP 1: Get JWT ---------------
def get_jwt():
    url = f"{BASE_URL}/jwt"
    params = {"email": EMAIL, "third_party_internal_id": USER_UID}
    response = requests.get(url, headers=auth_headers(), params=params)
    response.raise_for_status()
    return response.json()["token"]

# --------------- STEP 2: Create Session ---------------
def create_session(token):
    url = f"{BASE_URL}/sessions"
    response = requests.post(url, headers=auth_headers(token))
    response.raise_for_status()
    return response.json()["session_id"]


# --------------- STEP 3: Get Transcript ---------------
def get_transcript(token, session_id):
    url = f"{BASE_URL}/sessions/{session_id}/transcript"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json().get("transcript", "")

def update_session(token, session_id, transcript=None, notes_file_path=None):
    notes = []

    if notes_file_path:
        print("Got a notes file path:", notes_file_path)
        if os.path.isfile(notes_file_path):
            print("File exists, loading...")
            with open(notes_file_path, "r", encoding="utf-8") as f:
                notes += [line.strip() for line in f if line.strip()]
        else:
            print("File does NOT exist:", notes_file_path)
    else:
        print("No file path provided.")

    
    # Add transcript if provided
    if transcript:
        notes.append(f"Transcript: {transcript}")
    
    # Add fallback note
    if not notes:
        notes.append("Vitals are stable.")

    url = f"{BASE_URL}/sessions/{session_id}"
    data = {
        "duration": 10,
        "language_code": "en",
        "output_language_code": "en",
        "patient": {
            "name": "John Doe",
            "gender": "MALE",
            "dob": "1990-01-01"
        },
        "clinician_notes": notes,
        "generate_output_without_recording": True
    }
    response = requests.patch(url, headers=auth_headers(token), json=data)
    response.raise_for_status()
    return response.json()


# --------------- STEP 5: Generate Consult Note ---------------
def generate_consult_note(token, session_id):
    url = f"{BASE_URL}/sessions/{session_id}/consult-note"
    data = {
        "generation_method": "TEMPLATE",
        "addition": "",
        "template_id": TEMPLATE_ID,
        "voice_style": "GOLDILOCKS",
        "brain": "LEFT"
    }
    response = requests.post(url, headers=auth_headers(token), json=data, stream=True)
    response.raise_for_status()
    return stream_response_to_text(response)

def get_session_details(token, session_id):
    url = f"{BASE_URL}/sessions/{session_id}"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["session"]




# --------------- STEP 6: Ask AI to Summarise ---------------
def ask_heidi(token, session_id, content):
    url = f"{BASE_URL}/sessions/{session_id}/ask-ai"
    data = {
        "ai_command_text": "Summarise and note comorbidities, medications, allergies.",
        "content": content,
        "content_type": "MARKDOWN"
    }
    response = requests.post(url, headers=auth_headers(token), json=data, stream=True)
    response.raise_for_status()
    return stream_response_to_text(response)


# --------------- GET TEMPLATE ---------------
def get_templates(token):
    url = f"{BASE_URL}/templates/consult-note-templates"
    response = requests.get(url, headers=auth_headers(token))
    response.raise_for_status()
    return response.json()["templates"]

# --------------- CUSTOM TEMPLATE ---------------
def generate_custom_template(token, session_id, json_path="test.json"):
    with open(json_path, "r") as file:
        template_content = json.load(file)

    url = f"{BASE_URL}/sessions/{session_id}/client-customised-template/response"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    response = requests.post(url, headers=headers, json=template_content)
    response.raise_for_status()
    return response.json()


# --------------- STEP X: Upload Audio (Optional) ---------------
def upload_audio(token, session_id, audio_file_path):
    if not os.path.isfile(audio_file_path):
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

    url = f"{BASE_URL}/sessions/{session_id}/audio"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    with open(audio_file_path, "rb") as audio_file:
        files = {"file": audio_file}
        response = requests.post(url, headers=headers, files=files)
    response.raise_for_status()
    return response.json()


# --------------- MAIN EXECUTION ---------------
def main(audio_file_path=None, notes_file_path=None):
    print("Authenticating...")
    token = get_jwt()

    print("Creating session...")
    session_id = create_session(token)

    if audio_file_path:
        print(f"Uploading audio from {audio_file_path}...")
        upload_audio(token, session_id, audio_file_path)

    print("Fetching transcript...")
    transcript = get_transcript(token, session_id)

    print("Updating session with transcript and notes...")
    update_session(token, session_id, transcript, notes_file_path)

    print("Generating consult note...")
    note = generate_consult_note(token, session_id)

    print("Asking Heidi...")
    summary = ask_heidi(token, session_id, note)

    print("\n--- Summary ---\n", summary)

    print("Fetching session details...")
    session = get_session_details(token, session_id)
    consult_start = session.get("created_at")

    print(f"\n--- Consult Start Time ---\n{consult_start}")


if __name__ == "__main__":
    for i in range(1, 6):
        file_path = f"heidi_transcripts/john_doe_{i}.txt"
        print(f"\nProcessing file: {file_path}")
        main(notes_file_path=file_path)
