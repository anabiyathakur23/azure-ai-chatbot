
# Azure GPT-4o Chatbot

## Description
This is a basic chatbot built using **Azure OpenAI GPT-4o**. Users can interact with the chatbot via a console or web interface. The chatbot sends user messages to the GPT-4o model hosted on Azure and returns AI-generated responses.

---

## Features
- Interactive chatbot using GPT-4o
- Simple and functional backend logic
- Handles basic errors gracefully
- Easily configurable using environment variables

---

## Architecture
The chatbot architecture consists of:

1. **User Interface**: Console or web app where the user sends messages.
2. **Backend Server / Chatbot Logic**: Handles incoming requests, communicates with Azure OpenAI, and processes responses.
3. **Azure OpenAI GPT-4o**: Processes user inputs and generates AI responses.
4. **Data Flow**: Requests from the user go to the backend, which sends them to GPT-4o. Responses are then returned to the user.

A diagram illustrating this architecture is available in `assets/architecture.png`.

---

## Setup Instructions

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd chatbot-project
