// Client-side encryption and voting logic

const API_BASE_URL = 'http://localhost:5000'; // Change this to your server's URL

async function getServerPublicKey() {
    const response = await fetch(`${API_BASE_URL}/server_public_key`);
    const data = await response.json();
    return data.public_key;
}

function pemToArrayBuffer(pem) {
    const b64 = pem.replace(/-----BEGIN PUBLIC KEY-----|-----END PUBLIC KEY-----|\n|\r/g, '');
    return base64ToArrayBuffer(b64);
}

function base64ToArrayBuffer(base64) {
    const binary_string = window.atob(base64);
    const len = binary_string.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
        bytes[i] = binary_string.charCodeAt(i);
    }
    return bytes.buffer;
}

function arrayBufferToBase64(buffer) {
    let binary = '';
    const bytes = new Uint8Array(buffer);
    const len = bytes.byteLength;
    for (let i = 0; i < len; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return window.btoa(binary);
}


async function getVoteStatus() {
    const response = await fetch(`${API_BASE_URL}/status`);
    const data = await response.json();
    return data;
}

async function getVoteOptions() {
    try {
        const response = await fetch(`${API_BASE_URL}/vote_options`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error fetching vote options:', error);
        throw error;
    }
}


async function submitEncryptedVote(vote, signature, publicKey, keyType) {
    const votePackage = `${vote}:${signature}:${publicKey}:${keyType}`;
    const encodedVotePackage = btoa(votePackage);

    try {
        const response = await fetch(`${API_BASE_URL}/vote`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                vote_package: encodedVotePackage
            }),
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to submit vote');
        }

        const result = await response.json();
        return result;
    } catch (error) {
        console.error('Error submitting vote:', error);
        throw error;
    }
}

async function setupVote(options, authorizedKeys, adminPublicKey, durationHours) {
    try {
        const response = await fetch(`${API_BASE_URL}/setup`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                options: options,
                authorized_keys: authorizedKeys,
                admin_public_key: adminPublicKey,
                duration_hours: durationHours
            }),
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to setup vote');
        }

        const result = await response.json();
        return result;
    } catch (error) {
        console.error('Error setting up vote:', error);
        throw error;
    }
}

async function getResults() {
    const response = await fetch(`${API_BASE_URL}/results`);
    const result = await response.json();
    if (!response.ok) {
        throw new Error(result.error);
    }
    return result;
}

async function submitAdminDecision(encryptedDecision) {
    const response = await fetch(`${API_BASE_URL}/admin_decision`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            encrypted_decision: encryptedDecision
        }),
    });

    const result = await response.json();
    if (!response.ok) {
        throw new Error(result.error);
    }
    return result;
}

async function updateVoteStatus() {
    const submitVoteForm = document.getElementById('submitVoteForm');
    const voteMessage = document.getElementById('voteMessage');
    const voteOptionsContainer = document.getElementById('voteOptions');
    const resultsContainer = document.getElementById('results');

    try {
        const status = await getVoteStatus();
        if (status.status === "In progress") {
            submitVoteForm.style.display = 'block';
            voteMessage.textContent = `Voting is in progress. ${status.deadline ? `Deadline: ${new Date(status.deadline).toLocaleString()}` : ''}`;
            
            if (status.options && status.options.length > 0) {
                voteOptionsContainer.innerHTML = status.options.map(option => `<option value="${option}">${option}</option>`).join('');
            } else {
                voteOptionsContainer.innerHTML = '<option value="">No options available</option>';
                voteMessage.textContent += ' However, no voting options are currently available.';
            }
        } else if (status.status === "Completed") {
            submitVoteForm.style.display = 'none';
            voteMessage.textContent = "Voting has ended. Check the results below.";
            voteOptionsContainer.innerHTML = '<option value="">Voting completed</option>';
            
            // Fetch and display the results
            try {
                const results = await getResults();
                resultsContainer.textContent = JSON.stringify(results, null, 2);
            } catch (resultError) {
                resultsContainer.textContent = `Error fetching results: ${resultError.message}`;
            }
        } else {
            submitVoteForm.style.display = 'none';
            voteMessage.textContent = status.status === "Not set up" ? "No active vote at this time." : "Voting has ended.";
            voteOptionsContainer.innerHTML = '<option value="">No options available</option>';
        }
    } catch (error) {
        console.error('Error updating vote status:', error);
        voteMessage.textContent = `Error: ${error.message}`;
        submitVoteForm.style.display = 'none';
        voteOptionsContainer.innerHTML = '<option value="">Error loading options</option>';
    }
}


document.addEventListener('DOMContentLoaded', () => {
    const setupVoteForm = document.getElementById('setupVoteForm');
    const submitVoteForm = document.getElementById('submitVoteForm');
    const setupMessage = document.getElementById('setupMessage');
    const voteMessage = document.getElementById('voteMessage');
    setInterval(updateVoteStatus, 30000); // Update every 30 seconds
    updateVoteStatus();

    if (setupVoteForm) {
        setupVoteForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const options = document.getElementById('voteOptions').value.split(',').map(option => option.trim());
            const authorizedKeys = document.getElementById('authorizedKeys').value.split('\n').map(key => key.trim());
            const adminPublicKey = document.getElementById('adminPublicKey').value.trim();
            const durationHours = parseInt(document.getElementById('votingDuration').value);

            try {
                const result = await setupVote(options, authorizedKeys, adminPublicKey, durationHours);
                setupMessage.textContent = result.message;
                setupMessage.style.color = 'green';
                // Optionally, you can update the UI to reflect that a vote is now active
                updateVoteStatus();
            } catch (error) {
                setupMessage.textContent = `Error: ${error.message}`;
                setupMessage.style.color = 'red';
            }
        });
    }

    if (submitVoteForm) {
        submitVoteForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const votePackage = document.getElementById('votePackage').value;
            
            try {
                // Decode the vote package
                const decodedPackage = atob(votePackage);
                const [vote, signature, publicKey, keyType] = decodedPackage.split(':');

                const result = await submitEncryptedVote(vote, signature, publicKey, keyType);
                voteMessage.textContent = result.message;
                voteMessage.style.color = 'green';
                // Update vote status after submitting
                updateVoteStatus();
            } catch (error) {
                voteMessage.textContent = `Error: ${error.message}`;
                voteMessage.style.color = 'red';
            }
        });
    }

    if (getResultsButton) {
        getResultsButton.addEventListener('click', async () => {
            try {
                const result = await getResults();
                document.getElementById('results').textContent = JSON.stringify(result, null, 2);
            } catch (error) {
                document.getElementById('results').textContent = `Error: ${error.message}`;
            }
        });
    }

    if (adminDecisionForm) {
        adminDecisionForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const encryptedDecision = document.getElementById('encryptedAdminDecision').value;

            try {
                const result = await submitAdminDecision(encryptedDecision);
                document.getElementById('adminMessage').textContent = result.message;
            } catch (error) {
                document.getElementById('adminMessage').textContent = `Error: ${error.message}`;
            }
        });
    }
});