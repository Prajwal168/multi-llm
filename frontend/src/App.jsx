import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/atom-one-dark.css";
import "./App.css";

// LLM output sometimes indents a "sample output" snippet with spaces/tabs
// but no ``` fence. CommonMark treats that as an indented code block, and
// since it has no language it never gets syntax-highlighted — leaving
// dark-on-dark, unreadable text. Strip stray indentation on any line that
// isn't inside a real ``` fenced block so it just renders as plain text.
function sanitizeMarkdown(text) {
  if (!text) return text;

  let inFence = false;

  return text
    .split("\n")
    .map((line) => {
      if (line.trimStart().startsWith("```")) {
        inFence = !inFence;
        return line;
      }

      if (!inFence && /^( {4,}|\t)/.test(line)) {
        return line.replace(/^[ \t]+/, "");
      }

      return line;
    })
    .join("\n");
}

// =========================
// LOCAL PERSISTENCE
// =========================
//
// Everything the user can see in the sidebar/chat is kept in
// localStorage so a page refresh (or closing and reopening the tab)
// doesn't lose it. `history` is a list of chats; each chat holds its
// `messages` and its finished `runs` (the task + generated output
// panels). `activeChatId` (which chat is open) is persisted too.
//
// Only runs that reached the "final" stage are saved. A run that was
// still streaming when the page refreshed can't be resumed, so it is
// dropped (the user's message stays and can be resubmitted).
//
// Backend restart detection: the backend exposes GET /api/session which
// returns a boot_id that changes every time the server process starts.
// The boot_id seen last is stored under BOOT_ID_KEY. On page load, if the
// backend's boot_id differs from the stored one, all saved data is wiped
// and the app starts fresh. A plain page refresh keeps the same boot_id,
// so data survives.

const HISTORY_KEY = "multiLlmChatHistory";
const ACTIVE_CHAT_KEY = "multiLlmActiveChatId";
const BOOT_ID_KEY = "multiLlmBootId";

function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    console.error("Failed to load saved chat history:", error);
    return [];
  }
}

function loadActiveChatId() {
  try {
    const raw = localStorage.getItem(ACTIVE_CHAT_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (error) {
    console.error("Failed to load saved active chat id:", error);
    return null;
  }
}



function App() {
  // Both history and the active chat are initialized straight from
  // localStorage (via lazy useState initializers) so the very first
  // render after a refresh already shows the right chat instead of
  // flashing an empty state first.
  const [history, setHistory] = useState(loadHistory);
  const [activeChatId, setActiveChatId] = useState(loadActiveChatId);
  const [messages, setMessages] = useState(() => {
    const savedActiveId = loadActiveChatId();
    if (!savedActiveId) return [];
    const savedHistory = loadHistory();
    const activeChat = savedHistory.find((chat) => chat.id === savedActiveId);
    return activeChat?.messages || [];
  });

  const [query, setQuery] = useState("");

  const [processing, setProcessing] = useState(false);
  const [mediatorLoading, setMediatorLoading] = useState(false);
  const [awaitingApproval, setAwaitingApproval] = useState(false);

  const [rejected, setRejected] = useState(false);
  const [rejectedQuery, setRejectedQuery] = useState("");

  // Each entry is a self-contained processing panel for one query.
  // Once a run is pushed here it stays put; a new query pushes a new run.
  // Finished runs are restored from the active chat's saved `runs`.
  const [runs, setRuns] = useState(() => {
    const savedActiveId = loadActiveChatId();
    if (!savedActiveId) return [];
    const savedHistory = loadHistory();
    const activeChat = savedHistory.find((chat) => chat.id === savedActiveId);
    return activeChat?.runs || [];
  });

  // False until the backend boot_id check has finished, so we never
  // flash stale data that is about to be wiped.
  const [sessionChecked, setSessionChecked] = useState(false);

  const updateRun = (runId, updates) => {
    setRuns((prevRuns) =>
      prevRuns.map((run) =>
        run.id === runId ? { ...run, ...updates } : run
      )
    );
  };

  // =========================
  // PERSISTENCE EFFECTS
  // =========================

  // Compare the backend's boot_id with the one we saved. Different (or
  // none saved) means the backend was restarted -> start fresh. If the
  // backend is unreachable we keep whatever is saved.
  useEffect(() => {
    let cancelled = false;

    const checkSession = async () => {
      try {
        const res = await fetch("http://127.0.0.1:8000/api/session");
        if (!res.ok) {
          throw new Error(`Session check failed: ${res.status}`);
        }
        const { boot_id } = await res.json();
        if (cancelled) return;

        const storedBootId = localStorage.getItem(BOOT_ID_KEY);
        if (storedBootId !== boot_id) {
          localStorage.removeItem(HISTORY_KEY);
          localStorage.removeItem(ACTIVE_CHAT_KEY);
          localStorage.setItem(BOOT_ID_KEY, boot_id);

          setHistory([]);
          setActiveChatId(null);
          setMessages([]);
          setRuns([]);
        }
      } catch (error) {
        console.error("Session check failed:", error);
      } finally {
        if (!cancelled) setSessionChecked(true);
      }
    };

    checkSession();

    return () => {
      cancelled = true;
    };
  }, []);

  // Whenever the active chat's messages or runs change, keep that
  // chat's entry inside `history` in sync, so switching away and
  // coming back through the sidebar shows the full conversation
  // including each task's generated output.
  useEffect(() => {
    if (!activeChatId) return;

    // Only finished runs are saved; a half-streamed run can't be resumed.
    const finishedRuns = runs.filter((run) => run.stage === "final");

    setHistory((prevHistory) =>
      prevHistory.map((chat) =>
        chat.id === activeChatId
          ? { ...chat, messages, runs: finishedRuns }
          : chat
      )
    );
  }, [messages, runs, activeChatId]);

  // Persist history to localStorage every time it changes.
  useEffect(() => {
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
    } catch (error) {
      console.error("Failed to save chat history:", error);
    }
  }, [history]);

  // Persist which chat is active every time it changes, so a refresh
  // reopens the same conversation instead of landing on a blank page.
  useEffect(() => {
    try {
      if (activeChatId) {
        localStorage.setItem(ACTIVE_CHAT_KEY, JSON.stringify(activeChatId));
      } else {
        localStorage.removeItem(ACTIVE_CHAT_KEY);
      }
    } catch (error) {
      console.error("Failed to save active chat id:", error);
    }
  }, [activeChatId]);

  // =========================
  // SEND QUERY
  // =========================


const handleSubmit = async () => {
  if (
    !query.trim() ||
    processing ||
    awaitingApproval
  ) {
    return;
  }

  const userQuery = query.trim();

  const userMessage = {
    id: Date.now(),
    role: "user",
    content: userQuery,
  };
  const isNewConversation = !activeChatId;
  const chatId = isNewConversation ? Date.now() : activeChatId;

  const updatedMessages = isNewConversation
    ? [userMessage]
    : [...messages, userMessage];

  setActiveChatId(chatId);
  setMessages(updatedMessages);

  setHistory((prevHistory) => {
    if (isNewConversation) {
      return [
        ...prevHistory,
        {
          id: chatId,
          title:
            userQuery.slice(0, 30) +
            (userQuery.length > 30 ? "..." : ""),
          messages: [userMessage],
          runs: [],
        },
      ];
    }

    return prevHistory.map((chat) =>
      chat.id === activeChatId
        ? {
            ...chat,
            messages: updatedMessages,
          }
        : chat
    );
  });

  setQuery("");
  setRejected(false);
  setRejectedQuery("");



  // Start Mediator
  setProcessing(true);
  setMediatorLoading(true);
  

  try {
    // ==========================================
    // CALL FASTAPI MEDIATOR
    // ==========================================

    const response = await fetch(
      "http://127.0.0.1:8000/api/mediator",
      {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          query: userQuery,
        }),
      }
    );

    // ==========================================
    // CHECK HTTP RESPONSE
    // ==========================================

    if (!response.ok) {
      throw new Error(
        `Mediator request failed: ${response.status}`
      );
    }

    // ==========================================
    // READ BACKEND RESPONSE
    // ==========================================

    const data = await response.json();

    const result = data.result;

    // ==========================================
    // CONVERSATIONAL RESPONSE
    // ==========================================

    if (typeof result === "string") {

  setProcessing(false);
  setMediatorLoading(false);

  setMessages((currentMessages) => [
    ...currentMessages,
    {
      role: "assistant",
      content: result,
    },
  ]);

  return;
}

    // ==========================================
    // TASK-ORIENTED RESPONSE
    // ==========================================

    if (!Array.isArray(result)) {
      throw new Error(
        "Invalid Mediator response: expected a task list."
      );
    }

    // ==========================================
    // REAL MEDIATOR TASKS
    // ==========================================

   const newRun = {
      id: Date.now(),
      messageId: userMessage.id,
      stage: "mediator",
      expandedStage: "mediator",
      originalQuery: userQuery,
      generatedTasks: result,
      retrievalTasks: [],
      routedTasks: [],
      retrievalResults: [],
      executionPackages: [],
      results: [],
      taskProgress: {},
      activeRetrievalOperation: "planner",
    };

    setRuns((prevRuns) => [...prevRuns, newRun]);

    setProcessing(false);
    setMediatorLoading(false);

    setAwaitingApproval(true);
  } catch (error) {

    console.error(
      "Mediator request failed:",
      error
    );

    setProcessing(false);
    setMediatorLoading(false);

    setMessages((currentMessages) => [
      ...currentMessages,
      {
        role: "assistant",
        content:
          "Unable to connect to the Mediator backend. Please make sure the FastAPI server is running.",
      },
    ]);
  }
};

  // =========================
// CONTINUE
// =========================

const handleContinue = async (runId) => {

  const run = runs.find((r) => r.id === runId);
  if (!run) return;

  setAwaitingApproval(false);
  setProcessing(true);
  setRejected(false);

  // Start Retrieval & Context
  // Keep all operations collapsed while backend is working
  updateRun(runId, {
    stage: "retrieval",
    expandedStage: "retrieval",
    activeRetrievalOperation: null,
  });

  try {

    // ==========================================
    // CALL FASTAPI RETRIEVAL
    // ==========================================

    const response = await fetch(
      "http://127.0.0.1:8000/api/retrieval",
      {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          tasks: run.generatedTasks,
          raw_query: run.originalQuery,
        }),
      }
    );


    // ==========================================
    // CHECK HTTP RESPONSE
    // ==========================================

    if (!response.ok) {

      throw new Error(
        `Retrieval request failed: ${response.status}`
      );

    }


    // ==========================================
    // READ BACKEND RESPONSE
    // ==========================================

    const data = await response.json();

    console.log(
      "REAL RETRIEVAL RESPONSE:",
      data
    );


    // ==========================================
    // STORE REAL RETRIEVAL DATA
    // ==========================================

    updateRun(runId, {
      retrievalTasks: data.retrieval_plan,
      routedTasks: data.routed_plan,
      retrievalResults: data.retrieval_results,
      executionPackages: data.execution_packages,
    });

    // ==========================================
    // RETRIEVAL COMPLETE — MOVE TO EXECUTION
    // ==========================================

    updateRun(runId, {
      stage: "execution",
      expandedStage: "execution",
    });

    // ==========================================
    // CALL FASTAPI EXECUTION
    // ==========================================

    const executionResponse = await fetch(
      "http://127.0.0.1:8000/api/execution",
      {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          execution_packages: data.execution_packages,
        }),
      }
    );

    // ==========================================
    // CHECK HTTP RESPONSE
    // ==========================================

    if (!executionResponse.ok || !executionResponse.body) {

      throw new Error(
        `Execution request failed: ${executionResponse.status}`
      );

    }

    // ==========================================
    // READ STREAMED PROGRESS
    // (NDJSON: one JSON event per line)
    // ==========================================
    //
    // The backend streams events as each task executes and
    // verifies, instead of blocking until every task is done:
    //   {"type": "executed", "task_id": N}
    //   {"type": "verified", "task_id": N, "status", ...}
    //   {"type": "done", "results": [...]}   <- always last
    //
    // taskProgress drives the live tick marks in the Execution &
    // Verification panel; results (from "done") drives Final Response.

    const reader = executionResponse.body.getReader();
    const decoder = new TextDecoder();

    let buffer = "";
    let finalResults = [];
    const taskProgress = {};

    while (true) {

      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      // Last entry may be a partial line split across chunks —
      // hold it back until more data arrives.
      buffer = lines.pop();

      for (const line of lines) {

        if (!line.trim()) continue;

        const event = JSON.parse(line);

        if (event.type === "executed") {

          taskProgress[event.task_id] = "executed";
          updateRun(runId, { taskProgress: { ...taskProgress } });

        } else if (event.type === "verified") {

          taskProgress[event.task_id] = event.status;
          updateRun(runId, { taskProgress: { ...taskProgress } });

        } else if (event.type === "done") {

          finalResults = event.results;

        }
      }
    }

    // ==========================================
    // STORE REAL EXECUTION RESULTS
    // ==========================================

    updateRun(runId, {
      results: finalResults,
      taskProgress,
      stage: "final",
      expandedStage: "final",
    });

    // ==========================================
    // EXECUTION & VERIFICATION COMPLETE
    // ==========================================

    setProcessing(false);


  } catch (error) {

    console.error(
      "Retrieval/Execution request failed:",
      error
    );

    setProcessing(false);

    setRuns((prevRuns) =>
      prevRuns.filter((run) => run.id !== runId)
    );

    setMessages((currentMessages) => [
      ...currentMessages,
      {
        role: "assistant",
        content:
          "Unable to complete the retrieval or execution process. Please check the backend.",
      },
    ]);

  }
};


  // =========================
  // REJECT
  // =========================

  const handleReject = (runId) => {
  const lastUserMessage =
    [...messages]
      .reverse()
      .find(
        (message) =>
          message.role === "user"
      );

  const originalQuery =
    lastUserMessage?.content || "";

  setRejectedQuery(originalQuery);

  // Put the original query back into the input
  setQuery(originalQuery);

  // Stay in the same conversation
  setRejected(true);

  setAwaitingApproval(false);
  setProcessing(false);

  setRuns((prevRuns) =>
    prevRuns.filter((run) => run.id !== runId)
  );
};


  // =========================
  // START OVER
  // =========================

  const handleStartOver = () => {

    setQuery("");
    setRejected(false);
    setRejectedQuery("");

    setMessages([]);
    setActiveChatId(null);

    setRuns([]);

    setAwaitingApproval(false);
    setProcessing(false);
  };


  // =========================
  // NEW CHAT
  // =========================
  //
  // Clears the visible page for a fresh conversation. The chat that
  // was just active is NOT lost: its messages and finished runs are
  // already kept in sync inside `history` by the effect above, so it
  // stays exactly as it was and is reachable again from the sidebar
  // via openConversation.

  const handleNewChat = () => {

    setQuery("");
    setActiveChatId(null);

    setMessages([]);

    setRuns([]);

    setAwaitingApproval(false);
    setProcessing(false);

    setRejected(false);
    setRejectedQuery("");
  };


  // =========================
  // OPEN CHAT
  // =========================

  const openConversation = (chat) => {
    setActiveChatId(chat.id);
    setMessages(chat.messages || []);
    setRuns(chat.runs || []);
    setAwaitingApproval(false);
    setProcessing(false);
    setRejected(false);
  };


  // =========================
  // TOGGLE STAGE
  // =========================

  const toggleStage = (runId, stageName) => {

    setRuns((prevRuns) =>
      prevRuns.map((run) =>
        run.id === runId
          ? {
              ...run,
              expandedStage:
                run.expandedStage === stageName ? null : stageName,
            }
          : run
      )
    );
  };

  const toggleRetrievalOperation = (runId, operation) => {

    setRuns((prevRuns) =>
      prevRuns.map((run) =>
        run.id === runId
          ? {
              ...run,
              activeRetrievalOperation:
                run.activeRetrievalOperation === operation ? null : operation,
            }
          : run
      )
    );
  };


  // Wait for the backend boot_id check so stale data never flashes.
  if (!sessionChecked) return null;


  return (
    <div className="app">


      {/* =========================
          SIDEBAR
          ========================= */}

      <aside className="sidebar">

        <div className="sidebar-header">
          <h2>Multi-LLM</h2>
        </div>


        <button
          className="new-chat-button"
          onClick={handleNewChat}
          disabled={processing || awaitingApproval}
        >
          + New Chat
        </button>


        <div className="history">

          <p className="history-title">
            Recent
          </p>


          {history.length === 0 ? (

            <p className="empty-history">
              No conversations yet
            </p>

          ) : (

            history.map((chat) => (

              <button
                key={chat.id}
                className={`history-item ${
                  activeChatId === chat.id ? "active" : ""
                }`}
                onClick={() => openConversation(chat)}
                disabled={processing || awaitingApproval}
              >
                {chat.title}
              </button>

            ))

          )}

        </div>

      </aside>


      {/* =========================
          MAIN CHAT
          ========================= */}

      <main className="chat-area">


        <header className="chat-header">
          <h1>
            Multi-LLM Deliberation
          </h1>
        </header>


        {/* =========================
            CHAT CONTENT
            ========================= */}

        <section className="chat-content">


          {messages.length === 0 ? (

            <div className="welcome">

              <h2>
                How can I help you?
              </h2>

              <p>
                Ask a question and let the
                Multi-LLM system work on it.
              </p>

            </div>

          ) : (

            <div className="messages">

              {messages.map((message, index) => (

  <div key={message.id || index}>

    {/* =========================
        CHAT MESSAGE
        ========================= */}

    <div
      className={`message ${message.role}`}
    >

      <div className="message-label">

        {message.role === "user"
          ? "You"
          : "Assistant"}

      </div>

      <div className="message-content">

        {message.content}

      </div>

    </div>

    {message.role === "user" &&
      runs
        .filter((run) => run.messageId === message.id)
        .map((run) => (
            <div className="processing-panel" key={run.id}>


              <div className="processing-header">

                <h3>
                  Processing
                </h3>

              </div>


              {/* =====================
                  MEDIATOR
                  ===================== */}

              <div className="processing-stage">


                <button
                  className="stage-header"
                  onClick={() =>
                    toggleStage(run.id, "mediator")
                  }
                >

                  <div className="stage-title">

                    <span className="stage-status">

                      {run.stage === "mediator" && !awaitingApproval
                          ? "⟳"
                          : "✓"}

                    </span>


                    <span>
                      {run.stage !== "mediator" || awaitingApproval
                        ? "Mediator completed"
                        : "Mediator"}
                    </span>

                  </div>


                  <span className="stage-arrow">

                    {run.expandedStage === "mediator"
                      ? "▼"
                      : "▶"}

                  </span>

                </button>


                {run.expandedStage === "mediator" && (

                  <div className="stage-body">


                    {mediatorLoading &&
                      run.stage === "mediator" && (

                        <p className="processing-text">

                          Analyzing request...

                        </p>

                    )}


                    {run.generatedTasks.length > 0 && (

                      <div className="task-container">

                        <div className="task-heading">
                          <div>
                            <p className="task-title">
                              Generated Tasks
                            </p>

                            <p className="task-count">
                              {run.generatedTasks.length} tasks generated
                            </p>
                          </div>
                        </div>

                        <ol className="generated-task-list">

                          {run.generatedTasks.map(
                              (task) => (

                                <li key={task.task_id}>

                                  <span className="task-number">
                                    {task.task_id}
                                  </span>

                                  <span className="task-text">
                                    {task.task}
                                  </span>

                                </li>

                              )
                            )}

                        </ol>

                        {run.stage === "mediator" && awaitingApproval && (
                          <div className="approval-section">

                            <p className="approval-message">
                              Review the plan before continuing.
                            </p>

                            <div className="approval-buttons">

                              <button
                                className="continue-button"
                                onClick={() => handleContinue(run.id)}
                              >
                                Continue →
                              </button>

                              <button
                                className="reject-button"
                                onClick={() => handleReject(run.id)}
                              >
                                Reject
                              </button>

                            </div>

                          </div>
                        )}

                      </div>

                    )}

                  </div>

                )}

              </div>


              {/* =====================
                  RETRIEVAL
                  ===================== */}

              <div className="processing-stage">


                <button
                  className="stage-header"
                  onClick={() =>
                    toggleStage(run.id, "retrieval")
                  }
                >

                  <div className="stage-title">

                    <span className="stage-status">

                      {run.stage === "retrieval"
                        ? "⟳"
                        : run.stage === "execution" ||
                          run.stage === "final"
                        ? "✓"
                        : "○"}

                    </span>


                    <span>
                      Retrieval & Context
                    </span>

                  </div>


                  <span className="stage-arrow">

                    {run.expandedStage === "retrieval"
                      ? "▼"
                      : "▶"}

                  </span>

                </button>


                {run.expandedStage === "retrieval" && (
                  <div className="stage-body">
                    {/* Planner Operation */}
                    <div className="retrieval-operation">
                      <button
                        className="retrieval-operation-header"
                        onClick={() =>
                          toggleRetrievalOperation(run.id, "planner")
                        }
                      >
                        <div className="retrieval-operation-title">
                          <span className="retrieval-operation-status">
                            {run.activeRetrievalOperation === "planner"
                              ? "⟳"
                              : "✓"}
                          </span>
                          <div className="retrieval-operation-info">
                            <span className="retrieval-operation-name">
                              Retrieval Planner
                            </span>
                            <span className="retrieval-operation-summary">
                              {run.generatedTasks.length} tasks • {run.retrievalTasks.length} require retrieval
                            </span>
                          </div>
                        </div>
                        <span>
                          {run.activeRetrievalOperation === "planner"
                            ? "▼"
                            : "▶"}
                        </span>
                      </button>

                      {run.activeRetrievalOperation === "planner" && (
                        <div className="retrieval-operation-body">
                          <div className="retrieval-task-list">
                            {run.retrievalTasks.map((task) => (
                              <div
                                className="retrieval-task"
                                key={task.task_id}
                              >

                                <div className="retrieval-task-info">

                                  <span className="retrieval-task-id">
                                    Task {task.task_id}
                                  </span>

                                  <span className="retrieval-strategy">
                                    Retrieval required
                                  </span>

                                </div>

                                <span className="retrieval-task-status">
                                  ✓
                                </span>

                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Source Selection Operation */}
                    <div className="retrieval-operation">
                      <button
                        className="retrieval-operation-header"
                        onClick={() =>
                          toggleRetrievalOperation(run.id, "source")
                        }
                      >
                        <div className="retrieval-operation-title">
                          <span className="retrieval-operation-status">
                            {run.activeRetrievalOperation === "source"
                              ? "⟳"
                              : run.activeRetrievalOperation === "planner"
                              ? "○"
                              : "✓"}
                          </span>
                          <div className="retrieval-operation-info">
                            <span className="retrieval-operation-name">
                              Source Selection
                            </span>
                            <span className="source-selection-summary">
                              {run.routedTasks.length} sources selected
                            </span>
                          </div>
                        </div>
                        <span>
                          {run.activeRetrievalOperation === "source"
                            ? "▼"
                            : "▶"}
                        </span>
                      </button>

                      {run.activeRetrievalOperation === "source" && (
                        <div className="retrieval-operation-body">
                          <div className="source-task-list">
                            {run.routedTasks.map((task) => (
                              <div
                                className="source-task"
                                key={task.task_id}
                              >

                                <div className="source-task-info">

                                  <span className="source-task-id">
                                    Task {task.task_id}
                                  </span>

                                  <span className="source-task-strategy">
                                    {task.retrieval_source === "static"
                                      ? "Static retrieval"
                                      : task.retrieval_source === "dynamic"
                                      ? "Dynamic retrieval"
                                      : "Unknown source"}
                                  </span>

                                </div>

                                <span className="source-task-status">
                                  ✓
                                </span>

                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Retrieval Operation */}
                    <div className="retrieval-operation">
                      <button
                        className="retrieval-operation-header"
                        onClick={() =>
                          toggleRetrievalOperation(run.id, "retrieval")
                        }
                      >
                        <div className="retrieval-operation-title">
                          <span className="retrieval-operation-status">
                            {run.activeRetrievalOperation === "retrieval"
                              ? "⟳"
                              : run.activeRetrievalOperation === "planner" ||
                                run.activeRetrievalOperation === "source"
                              ? "○"
                              : "✓"}
                          </span>
                          <div className="retrieval-operation-info">
                            <span className="retrieval-operation-name">
                              Retrieval
                            </span>
                            <span className="retrieval-operation-summary">
                              {run.retrievalResults.length} tasks retrieved
                            </span>
                          </div>
                        </div>
                        <span>
                          {run.activeRetrievalOperation === "retrieval"
                            ? "▼"
                            : "▶"}
                        </span>
                      </button>

                      {run.activeRetrievalOperation === "retrieval" && (
                        <div className="retrieval-operation-body">
                          <div className="retrieval-results-list">
                            {run.retrievalResults.map((result) => {
                                      const routedTask = run.routedTasks.find(
                                        (task) => task.task_id === result.task_id
                                      );

                                      const plannedSource =
                                        routedTask?.retrieval_source;

                                      const actualSource =
                                        result.retrieval_source;

                                      const isFallback =
                                        plannedSource === "static" &&
                                        actualSource === "dynamic";

                                      const hasContext =
                                        result.retrieved_context &&
                                        result.retrieved_context.length > 0;

                                      return (
                                        <div
                                          className="retrieval-result"
                                          key={result.task_id}
                                        >

                                          <div className="retrieval-result-info">

                                            <span className="retrieval-result-task">
                                              Task {result.task_id}
                                            </span>

                                            {isFallback ? (
                                              <>
                                                <span className="retrieval-result-strategy">
                                                  Static retrieval
                                                </span>

                                                <span className="retrieval-result-message">
                                                  No relevant context found
                                                </span>

                                                <div className="retrieval-fallback">

                                                  <span className="fallback-arrow">
                                                    ↳
                                                  </span>

                                                  <span>
                                                    Fallback → Dynamic retrieval
                                                  </span>

                                                  {hasContext && (
                                                    <span className="fallback-context">
                                                      Context found ({result.retrieved_context.length} chunks)
                                                    </span>
                                                  )}

                                                </div>
                                              </>
                                            ) : (
                                              <>
                                                <span className="retrieval-result-strategy">
                                                  {actualSource === "static"
                                                    ? "Static retrieval"
                                                    : actualSource === "dynamic"
                                                    ? "Dynamic retrieval"
                                                    : "Unknown retrieval source"}
                                                </span>

                                                <span className="retrieval-result-message">
                                                  {hasContext
                                                    ? `Context found (${result.retrieved_context.length} chunks)`
                                                    : "No relevant context found"}
                                                </span>
                                              </>
                                            )}

                                          </div>

                                          <span className="retrieval-result-status">
                                            {hasContext ? "✓" : "✗"}
                                          </span>

                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
                              )}
                            </div>

                    {/* Context Building Operation */}
                      <div className="retrieval-operation">
                        <button
                          className="retrieval-operation-header"
                          onClick={() =>
                            toggleRetrievalOperation(run.id, "context")
                          }
                        >
                          <div className="retrieval-operation-title">

                            <span className="retrieval-operation-status">
                              {run.activeRetrievalOperation === "context"
                                ? "⟳"
                                : run.activeRetrievalOperation === "planner" ||
                                  run.activeRetrievalOperation === "source" ||
                                  run.activeRetrievalOperation === "retrieval"
                                ? "○"
                                : "✓"}
                            </span>

                            <div className="retrieval-operation-info">

                              <span className="retrieval-operation-name">
                                Context Building
                              </span>

                              <span className="context-operation-summary">
                                {run.executionPackages.length} execution packages prepared
                              </span>

                            </div>
                          </div>

                          <span>
                            {run.activeRetrievalOperation === "context"
                              ? "▼"
                              : "▶"}
                          </span>
                        </button>


                        {run.activeRetrievalOperation === "context" && (
                          <div className="retrieval-operation-body">

                            <div className="context-task-list">

                              {run.executionPackages.map((pkg) => {

                                const originalTask = run.generatedTasks.find(
                                  (task) => task.task_id === pkg.task_id
                                );

                                const hasContext =
                                  pkg.retrieved_context &&
                                  pkg.retrieved_context.length > 0;

                                const contextRequired =
                                  originalTask?.retrieval?.required === true;

                                return (
                                  <div
                                    className="context-task"
                                    key={pkg.task_id}
                                  >

                                    <div className="context-task-info">

                                      <span className="context-task-id">
                                        Task {pkg.task_id}
                                      </span>

                                      <span className="context-task-status-text">
                                        {contextRequired
                                          ? hasContext
                                            ? "Context attached"
                                            : "Context unavailable"
                                          : "No context required"}
                                      </span>

                                    </div>

                                    <span className="context-task-status">
                                      {contextRequired && !hasContext
                                        ? "✗"
                                        : "✓"}
                                    </span>

                                  </div>
                                );
                              })}

                            </div>

                          </div>
                        )}

                      </div>

                    
                  </div>
                )}

              </div>


              {/* =====================
                  EXECUTION
                  ===================== */}

              <div className="processing-stage">


                <button
                  className="stage-header"
                  onClick={() =>
                    toggleStage(run.id, "execution")
                  }
                >

                  <div className="stage-title">

                    <span className="stage-status">

                      {run.stage === "execution"
                        ? "⟳"
                        : run.stage === "final"
                        ? "✓"
                        : "○"}

                    </span>


                    <span>
                      Execution & Verification
                    </span>

                  </div>


                  <span className="stage-arrow">

                    {run.expandedStage === "execution"
                      ? "▼"
                      : "▶"}

                  </span>

                </button>


                {run.expandedStage === "execution" && (

                  <div className="stage-body">

                    {run.stage !== "execution" && run.stage !== "final" && (

                      <p className="processing-text">
                        Waiting for retrieval.
                      </p>

                    )}

                    {(run.stage === "execution" || run.stage === "final") && (

                      <div className="execution-task-list">

                        {run.generatedTasks.map((task) => {

                          const progress =
                            run.taskProgress?.[task.task_id];

                          const result = run.results.find(
                            (r) => r.task_id === task.task_id
                          );

                          const isPassed =
                            progress === "passed" ||
                            result?.status === "passed";

                          const isFailed =
                            progress === "failed" ||
                            progress === "unverified_failed" ||
                            progress === "error" ||
                            result?.status === "failed" ||
                            result?.status === "unverified_failed" ||
                            result?.status === "error";

                          const isExecuted = progress === "executed";

                          let statusDisplay = "○";
                          let metaText = null;

                          if (isFailed) {

                            statusDisplay = "✗";
                            metaText =
                              result?.reason ?? "Verification failed";

                          } else if (isPassed) {

                            statusDisplay = "✓✓";
                            metaText = result
                              ? `Verified (${result.attempts} attempt${
                                  result.attempts === 1 ? "" : "s"
                                })`
                              : "Verified";

                          } else if (isExecuted) {

                            // Single tick: output generated, now
                            // waiting on the verifier.
                            statusDisplay = "✓";
                            metaText = "Executed — verifying...";

                          } else if (run.stage === "execution") {

                            // Independent tasks in the same
                            // dependency level run concurrently, so
                            // several of these can show at once.
                            statusDisplay = "⟳";
                            metaText = "Running...";

                          }

                          return (
                            <div
                              className="execution-task"
                              key={task.task_id}
                            >

                              <div className="execution-task-info">

                                <span className="execution-task-id">
                                  Task {task.task_id}
                                </span>

                                <span className="execution-task-text">
                                  {task.task}
                                </span>

                                {metaText && (
                                  <span className="execution-task-meta">
                                    {metaText}
                                  </span>
                                )}

                              </div>

                              <span className="execution-task-status">
                                {statusDisplay}
                              </span>

                            </div>
                          );
                        })}

                      </div>

                    )}

                  </div>

                )}

              </div>


              {/* =====================
                  FINAL RESPONSE
                  ===================== */}

              <div className="processing-stage">


                <button
                  className="stage-header"
                  onClick={() =>
                    toggleStage(run.id, "final")
                  }
                >

                  <div className="stage-title">

                    <span className="stage-status">

                      {run.stage === "final"
                        ? "✓"
                        : "○"}

                    </span>


                    <span>
                      Final Response
                    </span>

                  </div>


                  <span className="stage-arrow">

                    {run.expandedStage === "final"
                      ? "▼"
                      : "▶"}

                  </span>

                </button>


                {run.expandedStage === "final" && (

                  <div className="stage-body">

                    {run.stage !== "final" && (

                      <p className="processing-text">
                        Waiting for execution.
                      </p>

                    )}

                    {run.stage === "final" && (

                      <div className="final-response-list">

                        {run.results.map((result) => {

                          // Fall back to the mediator's task text if
                          // the result object doesn't carry `task`.
                          const taskText =
                            result.task ||
                            run.generatedTasks.find(
                              (t) => t.task_id === result.task_id
                            )?.task;

                          return (

                          <div
                            className="final-response-item"
                            key={result.task_id}
                          >

                            <p className="final-response-task-label">
                              Task {result.task_id}
                              {result.type && (
                                <span className="final-response-task-type">
                                  {" "}· {result.type}
                                </span>
                              )}
                            </p>

                            {taskText && (
                              <p className="final-response-task-text">
                                {taskText}
                              </p>
                            )}

                            <div className="final-response-output">
                              <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                rehypePlugins={[rehypeHighlight]}
                              >
                                {sanitizeMarkdown(result.output)}
                              </ReactMarkdown>
                            </div>

                            {(result.status === "failed" ||
                              result.status === "unverified_failed" ||
                              result.status === "error") && (
                              <p className="final-response-status">
                                Verification failed: {result.reason}
                              </p>
                            )}

                          </div>

                          );
                        })}

                      </div>

                    )}

                  </div>

                )}

              </div>


            </div>
        ))}


  </div>

))}

              {mediatorLoading && (
                <div className="processing-indicator">
                  <div className="processing-spinner">
                    ⟳
                  </div>
                  <div className="processing-text">
                    <span className="processing-title">
                      Processing your request...
                    </span>
                    <span className="processing-subtitle">
                      Mediator is analyzing your query
                    </span>
                  </div>
                </div>
              )}

            </div>

          )}


          {/* =========================
              REJECTION MESSAGE
              ========================= */}

          {rejected && (

            <div className="rejection-panel">

              <div className="rejection-title">
                Task plan rejected
              </div>


              <p>
                The generated task plan was
                rejected. Your original query
                is still available below.
              </p>


              <div className="rejection-query">

                {rejectedQuery}

              </div>


              <div className="rejection-actions">
                <p className="rejection-hint">
                  Modify the query below and press Enter to try again.
                </p>
              </div>

            </div>

          )}



        </section>


        {/* =========================
            INPUT
            ========================= */}

        <div className="input-container">


          <textarea
            value={query}
            onChange={(e) =>
              setQuery(e.target.value)
            }
            onKeyDown={(e) => {

              if (
                e.key === "Enter" &&
                !e.shiftKey
              ) {

                e.preventDefault();

                handleSubmit();

              }

            }}
            placeholder="Ask anything..."
            rows="1"
            disabled={
              processing ||
              awaitingApproval
            }
          />


          <button
            className="send-button"
            onClick={handleSubmit}
            disabled={
              processing ||
              awaitingApproval
            }
          >
            ↑
          </button>

        </div>


        <p className="disclaimer">
          Multi-LLM Deliberation Framework
        </p>


      </main>

    </div>
  );
}

export default App;