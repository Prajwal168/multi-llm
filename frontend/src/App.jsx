import { useState } from "react";
import "./App.css";

function App() {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState([]);
  const [history, setHistory] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);

  const [processing, setProcessing] = useState(false);
  const [stage, setStage] = useState(null);
  const [generatedTasks, setGeneratedTasks] = useState([]);
  const [awaitingApproval, setAwaitingApproval] = useState(false);

  const [rejected, setRejected] = useState(false);
  const [rejectedQuery, setRejectedQuery] = useState("");

  const [expandedStage, setExpandedStage] = useState("mediator");
  const [retrievalTasks, setRetrievalTasks] = useState([]);
  const [routedTasks, setRoutedTasks] = useState([]);
  const [retrievalResults, setRetrievalResults] = useState([]);
  const [contextTasks, setContextTasks] = useState([]);
  const [executionPackages, setExecutionPackages] = useState([]);
  const [activeRetrievalOperation, setActiveRetrievalOperation] = useState("planner");


  // =========================
  // SEND QUERY
  // =========================

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
  setStage(null);
  setExpandedStage(null);

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

   setGeneratedTasks(result);

    setProcessing(false);

    setStage("mediator");
    setExpandedStage("mediator");

    setAwaitingApproval(true);
  } catch (error) {

    console.error(
      "Mediator request failed:",
      error
    );

    setProcessing(false);
    setStage(null);

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

const handleContinue = async () => {

  setAwaitingApproval(false);
  setProcessing(true);
  setRejected(false);

  // Start Retrieval & Context
  setStage("retrieval");
  setExpandedStage("retrieval");
  setActiveRetrievalOperation("planner");

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
          tasks: generatedTasks,
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
    console.log("REAL RETRIEVAL RESPONSE:", data);


    // ==========================================
    // STORE REAL RETRIEVAL DATA
    // ==========================================

    setRetrievalTasks(
      data.retrieval_plan
    );
    setRoutedTasks(
      data.routed_plan
    );

    setRetrievalResults(
      data.retrieval_results
    );

    setExecutionPackages(
      data.execution_packages
    );


    // ==========================================
    // MOVE THROUGH THE UI STAGES
    // ==========================================

    setActiveRetrievalOperation("source");

    setActiveRetrievalOperation("retrieval");

    setActiveRetrievalOperation("context");

    setActiveRetrievalOperation("packages");


    // ==========================================
    // RETRIEVAL COMPLETE
    // ==========================================

    setStage("execution");

    setExpandedStage("execution");

    setActiveRetrievalOperation(null);

  } catch (error) {

    console.error(
      "Retrieval request failed:",
      error
    );

    setProcessing(false);

    setStage(null);

    setActiveRetrievalOperation(null);

    setMessages((currentMessages) => [
      ...currentMessages,
      {
        role: "assistant",
        content:
          "Unable to complete the retrieval process. Please check the backend.",
      },
    ]);

  }
};


  // =========================
  // REJECT
  // =========================

  const handleReject = () => {
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

  setStage(null);
  setGeneratedTasks([]);

  setExpandedStage("mediator");
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

    setStage(null);
    setGeneratedTasks([]);

    setAwaitingApproval(false);
    setProcessing(false);

    setExpandedStage("mediator");
  };


  // =========================
  // NEW CHAT
  // =========================

  const handleNewChat = () => {

    setQuery("");
    setActiveChatId(null);

    setMessages([]);

    setStage(null);
    setGeneratedTasks([]);

    setAwaitingApproval(false);
    setProcessing(false);

    setRejected(false);
    setRejectedQuery("");

    setExpandedStage("mediator");
  };


  // =========================
  // OPEN CHAT
  // =========================

  const openConversation = (chat) => {
    setActiveChatId(chat.id);
    setMessages(chat.messages || []);
    setAwaitingApproval(false);
    setProcessing(false);
    setRejected(false);
    setStage("idle");
    setExpandedStage(null);
  };


  // =========================
  // TOGGLE STAGE
  // =========================

  const toggleStage = (stageName) => {

    setExpandedStage((current) =>
      current === stageName
        ? null
        : stageName
    );
  };

  const toggleRetrievalOperation = (operation) => {

    setActiveRetrievalOperation((current) =>
      current === operation
        ? null
        : operation
    );
  };


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

              {messages.map(
                (message, index) => (

                  <div
                    key={index}
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

                )
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


          {/* =========================
              PROCESSING PANEL
              ========================= */}

          {stage && (

            <div className="processing-panel">


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
                    toggleStage("mediator")
                  }
                >

                  <div className="stage-title">

                    <span className="stage-status">

                      {stage === "mediator" && !awaitingApproval
                          ? "⟳"
                          : "✓"}

                    </span>


                    <span>
                      {awaitingApproval
                        ? "Mediator completed"
                        : "Mediator"}
                    </span>

                  </div>


                  <span className="stage-arrow">

                    {expandedStage === "mediator"
                      ? "▼"
                      : "▶"}

                  </span>

                </button>


                {expandedStage === "mediator" && (

                  <div className="stage-body">


                    {processing &&
                      stage === "mediator" && (

                        <p className="processing-text">

                          Analyzing request...

                        </p>

                    )}


                    {generatedTasks.length > 0 && (

                      <div className="task-container">

                        <div className="task-heading">
                          <div>
                            <p className="task-title">
                              Generated Tasks
                            </p>

                            <p className="task-count">
                              {generatedTasks.length} tasks generated
                            </p>
                          </div>
                        </div>

                        <ol className="generated-task-list">

                          {generatedTasks.map(
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

                        {awaitingApproval && (
                          <div className="approval-section">

                            <p className="approval-message">
                              Review the plan before continuing.
                            </p>

                            <div className="approval-buttons">

                              <button
                                className="continue-button"
                                onClick={handleContinue}
                              >
                                Continue →
                              </button>

                              <button
                                className="reject-button"
                                onClick={handleReject}
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
                    toggleStage("retrieval")
                  }
                >

                  <div className="stage-title">

                    <span className="stage-status">

                      {stage === "retrieval"
                        ? "⟳"
                        : stage === "execution" ||
                          stage === "final"
                        ? "✓"
                        : "○"}

                    </span>


                    <span>
                      Retrieval & Context
                    </span>

                  </div>


                  <span className="stage-arrow">

                    {expandedStage === "retrieval"
                      ? "▼"
                      : "▶"}

                  </span>

                </button>


                {expandedStage === "retrieval" && (
                  <div className="stage-body">
                    {/* Planner Operation */}
                    <div className="retrieval-operation">
                      <button
                        className="retrieval-operation-header"
                        onClick={() =>
                          toggleRetrievalOperation("planner")
                        }
                      >
                        <div className="retrieval-operation-title">
                          <span className="retrieval-operation-status">
                            {activeRetrievalOperation === "planner"
                              ? "⟳"
                              : "✓"}
                          </span>
                          <div className="retrieval-operation-info">
                            <span className="retrieval-operation-name">
                              Retrieval Planner
                            </span>
                            <span className="retrieval-operation-summary">
                              {generatedTasks.length} tasks • {retrievalTasks.length} require retrieval
                            </span>
                          </div>
                        </div>
                        <span>
                          {activeRetrievalOperation === "planner"
                            ? "▼"
                            : "▶"}
                        </span>
                      </button>

                      {activeRetrievalOperation === "planner" && (
                        <div className="retrieval-operation-body">
                          <div className="retrieval-task-list">
                            {retrievalTasks.map((task) => (
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
                          toggleRetrievalOperation("source")
                        }
                      >
                        <div className="retrieval-operation-title">
                          <span className="retrieval-operation-status">
                            {activeRetrievalOperation === "source"
                              ? "⟳"
                              : activeRetrievalOperation === "planner"
                              ? "○"
                              : "✓"}
                          </span>
                          <div className="retrieval-operation-info">
                            <span className="retrieval-operation-name">
                              Source Selection
                            </span>
                            <span className="source-selection-summary">
                              {routedTasks.length} sources selected
                            </span>
                          </div>
                        </div>
                        <span>
                          {activeRetrievalOperation === "source"
                            ? "▼"
                            : "▶"}
                        </span>
                      </button>

                      {activeRetrievalOperation === "source" && (
                        <div className="retrieval-operation-body">
                          <div className="source-task-list">
                            {routedTasks.map((task) => (
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
                          toggleRetrievalOperation("retrieval")
                        }
                      >
                        <div className="retrieval-operation-title">
                          <span className="retrieval-operation-status">
                            {activeRetrievalOperation === "retrieval"
                              ? "⟳"
                              : activeRetrievalOperation === "planner" ||
                                activeRetrievalOperation === "source"
                              ? "○"
                              : "✓"}
                          </span>
                          <div className="retrieval-operation-info">
                            <span className="retrieval-operation-name">
                              Retrieval
                            </span>
                            <span className="retrieval-operation-summary">
                              {retrievalResults.length} tasks retrieved
                            </span>
                          </div>
                        </div>
                        <span>
                          {activeRetrievalOperation === "retrieval"
                            ? "▼"
                            : "▶"}
                        </span>
                      </button>

                      {activeRetrievalOperation === "retrieval" && (
                        <div className="retrieval-operation-body">
                          <div className="retrieval-results-list">
                            {retrievalResults.map((result) => {
                                      const routedTask = routedTasks.find(
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
                            toggleRetrievalOperation("context")
                          }
                        >
                          <div className="retrieval-operation-title">

                            <span className="retrieval-operation-status">
                              {activeRetrievalOperation === "context"
                                ? "⟳"
                                : activeRetrievalOperation === "planner" ||
                                  activeRetrievalOperation === "source" ||
                                  activeRetrievalOperation === "retrieval"
                                ? "○"
                                : "✓"}
                            </span>

                            <div className="retrieval-operation-info">

                              <span className="retrieval-operation-name">
                                Context Building
                              </span>

                              <span className="context-operation-summary">
                                {executionPackages.length} execution packages prepared
                              </span>

                            </div>
                          </div>

                          <span>
                            {activeRetrievalOperation === "context"
                              ? "▼"
                              : "▶"}
                          </span>
                        </button>


                        {activeRetrievalOperation === "context" && (
                          <div className="retrieval-operation-body">

                            <div className="context-task-list">

                              {executionPackages.map((pkg) => {

                                const originalTask = generatedTasks.find(
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
                    toggleStage("execution")
                  }
                >

                  <div className="stage-title">

                    <span className="stage-status">

                      {stage === "execution"
                        ? "⟳"
                        : stage === "final"
                        ? "✓"
                        : "○"}

                    </span>


                    <span>
                      Execution & Verification
                    </span>

                  </div>


                  <span className="stage-arrow">

                    {expandedStage === "execution"
                      ? "▼"
                      : "▶"}

                  </span>

                </button>


                {expandedStage === "execution" && (

                  <div className="stage-body">

                    <p className="processing-text">

                      {stage === "execution"
                        ? "Executing tasks and verifying results..."
                        : stage === "final"
                        ? "Execution and verification completed."
                        : "Waiting for retrieval."}

                    </p>

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
                    toggleStage("final")
                  }
                >

                  <div className="stage-title">

                    <span className="stage-status">

                      {stage === "final"
                        ? "✓"
                        : "○"}

                    </span>


                    <span>
                      Final Response
                    </span>

                  </div>


                  <span className="stage-arrow">

                    {expandedStage === "final"
                      ? "▼"
                      : "▶"}

                  </span>

                </button>


                {expandedStage === "final" && (

                  <div className="stage-body">

                    <p className="processing-text">

                      {stage === "final"
                        ? "Processing complete."
                        : "Waiting for execution."}

                    </p>

                  </div>

                )}

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