// Base URL for the local FastAPI server
const API_BASE_URL = "http://127.0.0.1:8000";

/**
 * Sends a legal question to the SATTAM AI RAG backend.
 * @param {string} question - The user's query about Indian law.
 * @returns {Promise<{answer: string, sources: Array}>} Response object with answer and source documents.
 */
export async function queryLegalAI(question) {
    if (!question || !question.trim()) {
        throw new Error("Question cannot be empty.");
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/chat`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                question: question.trim()
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Server error: ${response.status}`);
        }

        const data = await response.json();
        return {
            answer: data.answer,
            sources: data.sources || []
        };
    } catch (error) {
        console.error("API Error (queryLegalAI):", error);
        throw error;
    }
}

/**
 * Checks if the backend server is online and active.
 * @returns {Promise<boolean>}
 */
export async function checkBackendHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/`);
        return response.ok;
    } catch (error) {
        return false;
    }
}