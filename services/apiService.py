from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, ed25519
from cryptography.hazmat.primitives import hashes
import base64
from datetime import datetime, timedelta
import struct
import logging
from cryptography.exceptions import InvalidSignature

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # This allows all origins for all routes

# In-memory storage
votes = []
authorized_keys = {}
vote_options = []
admin_public_key = None
deadline = None
voting_result = None
is_vote_active = False

logging.basicConfig(level=logging.DEBUG)

# Generate a new RSA key pair for the server
server_private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048
)
server_public_key = server_private_key.public_key()

def verify_signature(public_key, signature, data, key_type):
    try:
        if key_type == "ed25519":
            public_key.verify(signature, data.encode())
        elif key_type == "rsa":
            public_key.verify(
                signature,
                data.encode(),
                padding.PKCS1v15(),
                hashes.SHA256()
            )
        return True
    except InvalidSignature:
        return False

def calculate_results():
    global voting_result

    vote_counts = {}
    for vote in votes:
        vote_counts[vote] = vote_counts.get(vote, 0) + 1
    
    max_votes = max(vote_counts.values())
    winners = [option for option, count in vote_counts.items() if count == max_votes]
    
    if len(winners) == 1:
        voting_result = {"winner": winners[0], "vote_counts": vote_counts}
    else:
        voting_result = {"tie": winners, "vote_counts": vote_counts}

def check_vote_completion():
    global is_vote_active
    if all(authorized_keys.values()) or (deadline and datetime.now() > deadline):
        is_vote_active = False
        calculate_results()

def parse_openssh_public_key(key_data):
    try:
        parts = key_data.split()
        if len(parts) < 2:
            raise ValueError("Invalid key format")

        key_type, key_data = parts[0], parts[1]
        if key_type != "ssh-ed25519":
            raise ValueError("Only Ed25519 keys are supported")

        decoded_data = base64.b64decode(key_data)
        key_parts = []
        idx = 0
        while idx < len(decoded_data):
            length = struct.unpack('>I', decoded_data[idx:idx+4])[0]
            idx += 4
            key_parts.append(decoded_data[idx:idx+length])
            idx += length

        if len(key_parts) != 2 or key_parts[0] != b'ssh-ed25519':
            raise ValueError("Invalid key structure")

        public_key_bytes = key_parts[1]
        if len(public_key_bytes) != 32:
            raise ValueError("Invalid public key length")

        return ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
    except Exception as e:
        raise ValueError(f"Could not parse OpenSSH public key: {str(e)}")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/setup', methods=['POST'])
def setup_vote():
    global vote_options, authorized_keys, admin_public_key, deadline, is_vote_active

    logging.debug(f"Received setup request: {request.json}")

    if is_vote_active:
        return jsonify({"error": "A vote is already in progress"}), 400

    data = request.json

    if 'options' not in data or 'authorized_keys' not in data or 'duration_hours' not in data:
        logging.error("Missing required fields in setup request")
        return jsonify({"error": "Missing required fields"}), 400

    vote_options = data['options']
    authorized_keys = {key: False for key in data['authorized_keys']}
    
    if 'admin_public_key' in data and data['admin_public_key']:
        try:
            admin_public_key = parse_openssh_public_key(data['admin_public_key'])
        except ValueError as e:
            logging.error(f"Invalid admin public key: {str(e)}")
            return jsonify({"error": str(e)}), 400
    else:
        admin_public_key = None

    try:
        duration_hours = int(data['duration_hours'])
        if duration_hours <= 0:
            raise ValueError("Duration must be positive")
        deadline = datetime.now() + timedelta(hours=duration_hours)
    except ValueError as e:
        logging.error(f"Invalid duration: {str(e)}")
        return jsonify({"error": f"Invalid duration: {str(e)}"}), 400

    is_vote_active = True
    logging.info("Vote setup successful")
    return jsonify({"message": "Vote setup successful"}), 200

@app.route('/submit_vote')
def submit_vote_page():
    return render_template('submit_vote.html')

@app.route('/vote', methods=['POST', 'OPTIONS'])
def submit_vote():
    global is_vote_active, voting_result

    if request.method == "OPTIONS":
        return jsonify({}), 200
    
    if not is_vote_active:
        return jsonify({"error": "No active vote at this time"}), 400

    if deadline is None or datetime.now() > deadline:
        is_vote_active = False
        return jsonify({"error": "Voting deadline has passed"}), 400

    if not vote_options:
        return jsonify({"error": "Voting has not been set up correctly"}), 400

    data = request.json
    if 'vote_package' not in data:
        return jsonify({"error": "Missing vote package"}), 400

    try:
        vote_package = base64.b64decode(data['vote_package']).decode()
        vote, signature, public_key_str, key_type = vote_package.split(':')
    except:
        return jsonify({"error": "Invalid vote package format"}), 400
    
    public_key_bytes = base64.b64decode(public_key_str)

    if vote not in vote_options:
        return jsonify({"error": "Invalid vote option"}), 400

    # Load the public key based on its type
    verified = False
    for authorized_key in authorized_keys:
        try:
            if key_type == "ed25519":
                verified = verify_signature(authorized_key, signature, vote, key_type)
                if verified:
                    break
            elif key_type == "rsa":
                verified = verify_signature(authorized_key, signature, vote, key_type)
                if verified:
                    break
                # public_key = rsa.RSAPublicKey.from_public_bytes(public_key_bytes)
            else:
                return jsonify({"error": "Unsupported key type"}), 400
        except:
            continue

    if public_key_str in authorized_keys and authorized_keys[public_key_str]:
        return jsonify({"error": "Already voted"}), 400

    # Mark as voted and store the vote
    authorized_keys[public_key_str] = True
    votes.append(vote)

    # Check if all authorized users have voted
    if all(authorized_keys.values()):
        is_vote_active = False
        calculate_results()

    return jsonify({"message": "Vote submitted successfully"}), 200

@app.route('/status', methods=['GET'])
def get_status():
    check_vote_completion()
    if not vote_options:
        return jsonify({"status": "Not set up"})
    elif is_vote_active:
        return jsonify({
            "status": "In progress",
            "deadline": deadline.isoformat() if deadline else None,
            "options": vote_options
        })
    else:
        return jsonify({"status": "Completed"})

@app.route('/results', methods=['GET'])
def get_results():
    check_vote_completion()
    if voting_result is None:
        return jsonify({"error": "No votes have been cast or voting is still in progress"}), 400

    if "tie" in voting_result and admin_public_key is not None:
        return jsonify({"message": "Tie detected. Waiting for admin decision.", "results": voting_result}), 200

    return jsonify(voting_result), 200

@app.route('/status', methods=['GET'])
def get_vote_status():
    if not is_vote_active:
        return jsonify({"status": "No active vote"})
    elif datetime.now() < deadline:
        return jsonify({
            "status": "In progress",
            "deadline": deadline.isoformat(),
            "options": vote_options
        })
    else:
        return jsonify({"status": "Completed"})

@app.route('/vote_options', methods=['GET'])
def get_vote_options():
    if not is_vote_active:
        return jsonify([])  # Return an empty array instead of an error
    return jsonify(vote_options)

@app.route('/admin_decision', methods=['POST'])
def admin_decision():
    global voting_result

    if voting_result is None or "winner" in voting_result:
        return jsonify({"error": "Admin decision is not needed at this time"}), 400

    data = request.json
    encrypted_decision = base64.b64decode(data['encrypted_decision'])

    # Decrypt the admin's decision
    try:
        decision = server_private_key.decrypt(
            encrypted_decision,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        ).decode()
    except:
        return jsonify({"error": "Unable to decrypt admin decision"}), 400

    if decision not in voting_result["tie"]:
        return jsonify({"error": "Invalid decision"}), 400

    voting_result["winner"] = decision
    voting_result["message"] = "Tie resolved by admin decision"

    return jsonify({"message": "Admin decision recorded", "winner": decision}), 200

@app.route('/server_public_key', methods=['GET'])
def get_server_public_key():
    public_key_pem = server_public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return jsonify({"public_key": public_key_pem.decode()})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')