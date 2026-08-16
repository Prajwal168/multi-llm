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
  const [retrievalResults, setRetrievalResults] = useState([]);
  const [contextTasks, setContextTasks] = useState([]);
  const [executionPackages, setExecutionPackages] = useState([]);
  const [activeRetrievalOperation, setActiveRetrievalOperation] = useState("planner");


  // =========================
  // SEND QUERY
  // =========================

  const handleSubmit = () => {
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
          ? { ...chat, messages: updatedMessages }
          : chat
      );
    });

    setQuery("");
    setRejected(false);
    setRejectedQuery("");

    // Start Mediator
    setProcessing(true);
    setStage("mediator");
    setExpandedStage("mediator");

    // Temporary Mediator simulation
    setTimeout(() => {

      const tasks = [
        `Understand the request: ${userQuery}`,
        "Retrieve relevant information",
        "Generate and verify the final response",
      ];

      setGeneratedTasks(tasks);
      setProcessing(false);
      setAwaitingApproval(true);
      setExpandedStage("mediator");

    }, 1200);
  };


  // =========================
  // CONTINUE
  // =========================

  const handleContinue = () => {
    setAwaitingApproval(false);
    setProcessing(true);
    setRejected(false);

    const retrievalPlan = [
      {
        taskId: 1,
        strategy: "Static retrieval",
        required: true,
        status: "processing",
      },
      {
        taskId: 2,
        strategy: "Static retrieval",
        required: true,
        status: "waiting",
      },
      {
        taskId: 3,
        strategy: "No retrieval required",
        required: false,
        status: "completed",
      },
      {
        taskId: 4,
        strategy: "No retrieval required",
        required: false,
        status: "completed",
      },
      {
        taskId: 5,
        strategy: "Static retrieval",
        required: true,
        status: "waiting",
      },
    ];

    setRetrievalTasks(retrievalPlan);

    const retrievalResultsData = [
      {
        taskId: 1,
        strategy: "Static retrieval",
        status: "completed",
        result: "Context found",
        fallback: false,
      },
      {
        taskId: 2,
        strategy: "Static retrieval",
        status: "completed",
        result: "Context found",
        fallback: false,
      },
      {
        taskId: 5,
        strategy: "Static retrieval",
        status: "fallback",
        result: "No relevant context found",
        fallback: true,
        fallbackStrategy: "Dynamic retrieval",
        fallbackStatus: "completed",
        fallbackResult: "Context found",
      },
    ];

    setRetrievalResults(retrievalResultsData);

    const packages = [
      {
        taskId: 1,
        context: true,
        status: "completed",
        message: "Context attached",
      },
      {
        taskId: 2,
        context: true,
        status: "completed",
        message: "Context attached",
      },
      {
        taskId: 3,
        context: false,
        status: "completed",
        message: "No context required",
      },
      {
        taskId: 4,
        context: false,
        status: "completed",
        message: "No context required",
      },
      {
        taskId: 5,
        context: true,
        status: "completed",
        message: "Context attached",
      },
    ];

    setExecutionPackages(packages);

    // Start Retrieval & Context
    setStage("retrieval");
    setExpandedStage("retrieval");
    setActiveRetrievalOperation("planner");

    // 1 → Retrieval Planner
    setTimeout(() => {
      setActiveRetrievalOperation("source");
    }, 1800);

    // 2 → Source Selection
    setTimeout(() => {
      setActiveRetrievalOperation("retrieval");
    }, 3600);

    // 3 → Retrieval
    setTimeout(() => {
      setActiveRetrievalOperation("context");
    }, 5400);

    // 4 → Context Building
    setTimeout(() => {
      setActiveRetrievalOperation("packages");
    }, 7200);

    // 5 → Execution Packages finished
    setTimeout(() => {
      setStage("execution");
      setExpandedStage("execution");
      setActiveRetrievalOperation(null);
    }, 9000);
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
                            (task, index) => (

                              <li key={index}>
                                <span className="task-number">
                                  {index + 1}
                                </span>

                                <span className="task-text">
                                  {task}
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
                              5 tasks • 3 require retrieval
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
                                key={task.taskId}
                              >
                                <div className="retrieval-task-info">
                                  <span className="retrieval-task-id">
                                    Task {task.taskId}
                                  </span>
                                  <span className="retrieval-strategy">
                                    {task.required
                                      ? "Retrieval required"
                                      : "No retrieval required"}
                                  </span>
                                </div>
                                <span className="retrieval-task-status">
                                  {task.status === "processing"
                                    ? "⟳"
                                    : task.status === "completed"
                                    ? "✓"
                                    : "○"}
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
                            <span className="retrieval-operation-summary">
                              3 sources selected
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
                            {retrievalTasks
                              .filter((task) => task.required)
                              .map((task) => (
                                <div
                                  className="source-task"
                                  key={task.taskId}
                                >
                                  <div className="source-task-info">
                                    <span className="source-task-id">
                                      Task {task.taskId}
                                    </span>
                                    <span className="source-task-strategy">
                                      {task.strategy}
                                    </span>
                                  </div>
                                  <span className="source-task-status">
                                    ○
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
                              3 tasks retrieved • 1 fallback
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
                            {retrievalResults.map((task) => (
                              <div
                                className="retrieval-result"
                                key={task.taskId}
                              >
                                <div className="retrieval-result-info">
                                  <span className="retrieval-result-task">
                                    Task {task.taskId}
                                  </span>
                                  <span className="retrieval-result-strategy">
                                    {task.strategy}
                                  </span>
                                  <span className="retrieval-result-message">
                                    {task.result}
                                  </span>
                                  {task.fallback && (
                                    <div className="retrieval-fallback">
                                      <span className="fallback-arrow">
                                        ↳
                                      </span>
                                      <div className="fallback-info">
                                        <span className="fallback-label">
                                          Fallback → {task.fallbackStrategy}
                                        </span>
                                        <span className="fallback-status-text">
                                          Retrieving context...
                                        </span>
                                      </div>
                                    </div>
                                  )}
                                </div>
                                <span className="retrieval-result-status">
                                  {task.status === "completed"
                                    ? "✓"
                                    : task.status === "fallback"
                                    ? "✗"
                                    : "○"}
                                </span>
                              </div>
                            ))}
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
                            <span className="retrieval-operation-summary">
                              3 contexts prepared
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
                            {retrievalResults.map((task) => (
                              <div
                                className="context-task"
                                key={task.taskId}
                              >
                                <div className="context-task-info">
                                  <span className="context-task-id">
                                    Task {task.taskId}
                                  </span>
                                  <span className="context-task-message">
                                    Context prepared
                                  </span>
                                </div>
                                <span className="context-task-status">
                                  ✓
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Execution Packages Operation */}
                    <div className="retrieval-operation">
                      <button
                        className="retrieval-operation-header"
                        onClick={() =>
                          toggleRetrievalOperation("packages")
                        }
                      >
                        <div className="retrieval-operation-title">
                          <span className="retrieval-operation-status">
                            {activeRetrievalOperation === "packages"
                              ? "⟳"
                              : activeRetrievalOperation === "planner" ||
                                activeRetrievalOperation === "source" ||
                                activeRetrievalOperation === "retrieval" ||
                                activeRetrievalOperation === "context"
                              ? "○"
                              : "✓"}
                          </span>
                          <div className="retrieval-operation-info">
                            <span className="retrieval-operation-name">
                              Execution Packages
                            </span>
                            <span className="retrieval-operation-summary">
                              5 packages prepared
                            </span>
                          </div>
                        </div>
                        <span>
                          {activeRetrievalOperation === "packages"
                            ? "▼"
                            : "▶"}
                        </span>
                      </button>

                      {activeRetrievalOperation === "packages" && (
                        <div className="retrieval-operation-body">
                          <div className="execution-package-list">
                            {executionPackages.map((pkg) => (
                              <div
                                className="execution-package"
                                key={pkg.taskId}
                              >
                                <div className="execution-package-info">
                                  <span className="execution-package-task">
                                    Task {pkg.taskId}
                                  </span>
                                  <span className="execution-package-message">
                                    {pkg.message}
                                  </span>
                                </div>
                                <span className="execution-package-status">
                                  ✓
                                </span>
                              </div>
                            ))}
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