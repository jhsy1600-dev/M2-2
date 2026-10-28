import axios from "axios";
import "./style.css";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const chatBox = document.querySelector("#chat-box");
const chatForm = document.querySelector("#chat-form");
const chatInput = document.querySelector("#chat-input");
const chatSubmitBtn = document.querySelector("#chat-submit-btn");
const chatLoading = document.querySelector("#chat-loading");

const summaryBox = document.querySelector("#summary-box");
const loadSummaryBtn = document.querySelector("#load-summary-btn");

const dataForm = document.querySelector("#data-form");
const dateInput = document.querySelector("#date-input");
const valueInput = document.querySelector("#value-input");
const memoInput = document.querySelector("#memo-input");
const loadDataBtn = document.querySelector("#load-data-btn");
const dataList = document.querySelector("#data-list");

const loadConversationsBtn = document.querySelector("#load-conversations-btn");
const conversationList = document.querySelector("#conversation-list");

/**
 * HTML 특수문자 변환
 * 사용자 입력이나 AI 응답을 안전하게 화면에 표시하기 위함
 */
function escapeHtml(text) {
  return String(text ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

/**
 * 간단한 마크다운 렌더링 함수
 *
 * 지원하는 문법:
 * # 제목
 * ## 제목
 * ### 제목
 * **굵게**
 * `인라인 코드`
 * ```코드블록```
 * ---
 * - 목록
 * * 목록
 * 1. 숫자 목록
 * 줄바꿈
 */
function renderMarkdown(text) {
  let safeText = escapeHtml(text);

  // 코드블록
  safeText = safeText.replace(
    /```([\s\S]*?)```/g,
    "<pre><code>$1</code></pre>"
  );

  // 인라인 코드
  safeText = safeText.replace(/`([^`]+)`/g, "<code>$1</code>");

  // 제목
  safeText = safeText.replace(/^### (.*$)/gim, "<h3>$1</h3>");
  safeText = safeText.replace(/^## (.*$)/gim, "<h2>$1</h2>");
  safeText = safeText.replace(/^# (.*$)/gim, "<h1>$1</h1>");

  // 굵게
  safeText = safeText.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

  // 구분선
  safeText = safeText.replace(/^---$/gim, "<hr>");

  // 순서 없는 목록
  safeText = safeText.replace(/^\s*[-*]\s+(.*$)/gim, "• $1");

  // 숫자 목록
  safeText = safeText.replace(
    /^\s*(\d+)\.\s+(.*$)/gim,
    "<strong>$1.</strong> $2"
  );

  // 줄바꿈
  safeText = safeText.replace(/\n/g, "<br>");

  return safeText;
}

/**
 * 배열 응답 정리
 * 백엔드가 배열 그대로 주거나 { data: [] } 형태로 줘도 대응
 */
function normalizeArray(responseData) {
  if (Array.isArray(responseData)) return responseData;
  if (Array.isArray(responseData?.data)) return responseData.data;
  if (Array.isArray(responseData?.items)) return responseData.items;
  if (Array.isArray(responseData?.conversations)) {
    return responseData.conversations;
  }
  return [];
}

/**
 * 채팅 메시지를 화면에 추가
 */
function addMessage(role, content) {
  const messageDiv = document.createElement("div");
  messageDiv.classList.add("message");

  if (role === "user") {
    messageDiv.classList.add("user");
    messageDiv.innerHTML = `<strong>나:</strong> ${renderMarkdown(content)}`;
  } else {
    messageDiv.classList.add("ai");
    messageDiv.innerHTML = `<strong>AI:</strong> ${renderMarkdown(content)}`;
  }

  chatBox.appendChild(messageDiv);
  chatBox.scrollTop = chatBox.scrollHeight;
}

/**
 * 요약 데이터를 보기 좋게 표시
 */
function renderSummary(data) {
  if (!data) {
    return "요약 데이터가 없습니다.";
  }

  if (typeof data === "string") {
    return renderMarkdown(data);
  }

  const summaryText =
    data.summary ||
    data.message ||
    data.result ||
    data.answer ||
    data.reply;

  if (summaryText) {
    return renderMarkdown(summaryText);
  }

  const total =
    data.total ??
    data.total_value ??
    data.totalStudyTime ??
    data.total_study_time;

  const count =
    data.count ??
    data.data_count ??
    data.recordCount ??
    data.record_count;

  const average =
    data.average ??
    data.avg ??
    data.average_value ??
    data.averageStudyTime ??
    data.average_study_time;

  let html = "";

  if (total !== undefined) {
    html += `<p><strong>총 학습 시간:</strong> ${escapeHtml(total)}</p>`;
  }

  if (count !== undefined) {
    html += `<p><strong>기록 개수:</strong> ${escapeHtml(count)}</p>`;
  }

  if (average !== undefined) {
    html += `<p><strong>평균 학습 시간:</strong> ${escapeHtml(average)}</p>`;
  }

  if (html) return html;

  // 위 필드들이 없으면 객체 전체를 보기 좋게 표시
  return `<pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
}

/**
 * AI 채팅 요청
 */
chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const message = chatInput.value.trim();

  if (!message) {
    alert("질문을 입력해주세요.");
    return;
  }

  addMessage("user", message);
  chatInput.value = "";

  chatLoading.classList.remove("hidden");
  chatSubmitBtn.disabled = true;

  try {
    const response = await axios.post(`${API_BASE_URL}/api/chat`, {
      message
    });

    const aiAnswer =
      response.data.answer ||
      response.data.reply ||
      response.data.response ||
      response.data.message ||
      "AI 응답을 불러왔습니다.";

    addMessage("ai", aiAnswer);

    // 새 대화가 저장되었을 수 있으므로 대화 목록 갱신
    loadConversations();
  } catch (error) {
    console.error(error);
    addMessage("ai", "오류가 발생했습니다. 잠시 후 다시 시도해주세요.");
  } finally {
    chatLoading.classList.add("hidden");
    chatSubmitBtn.disabled = false;
    chatInput.focus();
  }
});

/**
 * 데이터 요약 불러오기
 */
async function loadSummary() {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/data/summary`);
    summaryBox.innerHTML = renderSummary(response.data);
  } catch (error) {
    console.error(error);
    summaryBox.textContent = "요약 정보를 불러오지 못했습니다.";
  }
}

loadSummaryBtn.addEventListener("click", loadSummary);

/**
 * 데이터 추가
 */
dataForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const date = dateInput.value;
  const value = Number(valueInput.value);
  const memo = memoInput.value.trim();

  if (!date) {
    alert("날짜를 입력해주세요.");
    return;
  }

  if (Number.isNaN(value)) {
    alert("학습 시간은 숫자로 입력해주세요.");
    return;
  }

  try {
    await axios.post(`${API_BASE_URL}/api/data`, {
      date,
      value,
      memo
    });

    alert("데이터가 추가되었습니다.");

    dateInput.value = "";
    valueInput.value = "";
    memoInput.value = "";

    await loadData();
    await loadSummary();
  } catch (error) {
    console.error(error);
    alert("데이터 추가 중 오류가 발생했습니다.");
  }
});

/**
 * 데이터 목록 불러오기
 */
async function loadData() {
  dataList.innerHTML = "";

  try {
    const response = await axios.get(`${API_BASE_URL}/api/data`);
    const items = normalizeArray(response.data);

    if (items.length === 0) {
      dataList.innerHTML = "<li>아직 등록된 데이터가 없습니다.</li>";
      return;
    }

    items.forEach((item) => {
      const li = document.createElement("li");

      const textSpan = document.createElement("span");
      textSpan.textContent = `${item.date || "날짜 없음"} / ${
        item.value ?? 0
      }시간 / ${item.memo || ""} `;

      const editBtn = document.createElement("button");
      editBtn.textContent = "수정";
      editBtn.style.marginLeft = "8px";

      editBtn.addEventListener("click", async () => {
        const newValue = prompt("수정할 학습 시간을 입력하세요.", item.value);

        if (newValue === null) return;

        const parsedValue = Number(newValue);

        if (Number.isNaN(parsedValue)) {
          alert("숫자를 입력해주세요.");
          return;
        }

        const newMemo = prompt("수정할 메모를 입력하세요.", item.memo || "");

        if (newMemo === null) return;

        try {
          await axios.put(`${API_BASE_URL}/api/data/${item.id}`, {
            date: item.date,
            value: parsedValue,
            memo: newMemo
          });

          alert("수정되었습니다.");

          await loadData();
          await loadSummary();
        } catch (error) {
          console.error(error);
          alert("수정 중 오류가 발생했습니다.");
        }
      });

      const deleteBtn = document.createElement("button");
      deleteBtn.textContent = "삭제";
      deleteBtn.style.marginLeft = "6px";

      deleteBtn.addEventListener("click", async () => {
        if (!confirm("정말 삭제하시겠습니까?")) return;

        try {
          await axios.delete(`${API_BASE_URL}/api/data/${item.id}`);

          alert("삭제되었습니다.");

          await loadData();
          await loadSummary();
        } catch (error) {
          console.error(error);
          alert("삭제 중 오류가 발생했습니다.");
        }
      });

      li.appendChild(textSpan);
      li.appendChild(editBtn);
      li.appendChild(deleteBtn);

      dataList.appendChild(li);
    });
  } catch (error) {
    console.error(error);
    dataList.innerHTML = "<li>데이터를 불러오지 못했습니다.</li>";
  }
}

loadDataBtn.addEventListener("click", loadData);

/**
 * 대화 목록 불러오기
 */
async function loadConversations() {
  conversationList.innerHTML = "";

  try {
    const response = await axios.get(`${API_BASE_URL}/api/conversations`);
    const conversations = normalizeArray(response.data);

    if (conversations.length === 0) {
      conversationList.innerHTML = "<li>저장된 대화 기록이 없습니다.</li>";
      return;
    }

    conversations.forEach((conversation) => {
      const li = document.createElement("li");

      const title =
        conversation.title ||
        conversation.created_at ||
        conversation.createdAt ||
        conversation.id ||
        "대화 기록";

      const titleSpan = document.createElement("span");
      titleSpan.textContent = `${title} `;

      const loadBtn = document.createElement("button");
      loadBtn.textContent = "불러오기";

      loadBtn.addEventListener("click", async () => {
        await loadConversationDetail(conversation);
      });

      const deleteBtn = document.createElement("button");
      deleteBtn.textContent = "삭제";
      deleteBtn.style.marginLeft = "6px";

      deleteBtn.addEventListener("click", async () => {
        if (!confirm("이 대화를 삭제하시겠습니까?")) return;

        try {
          await axios.delete(
            `${API_BASE_URL}/api/conversations/${conversation.id}`
          );

          alert("대화가 삭제되었습니다.");
          await loadConversations();
        } catch (error) {
          console.error(error);
          alert("대화 삭제 중 오류가 발생했습니다.");
        }
      });

      li.appendChild(titleSpan);
      li.appendChild(loadBtn);
      li.appendChild(deleteBtn);

      conversationList.appendChild(li);
    });
  } catch (error) {
    console.error(error);
    conversationList.innerHTML = "<li>대화 기록을 불러오지 못했습니다.</li>";
  }
}

loadConversationsBtn.addEventListener("click", loadConversations);

/**
 * 특정 대화 불러오기
 */
async function loadConversationDetail(conversation) {
  chatBox.innerHTML = "";

  try {
    let messages = conversation.messages;

    if (!messages && conversation.id) {
      const response = await axios.get(
        `${API_BASE_URL}/api/conversations/${conversation.id}`
      );

      messages =
        response.data.messages ||
        response.data.data?.messages ||
        response.data.conversation?.messages;
    }

    if (!messages || messages.length === 0) {
      addMessage("ai", "저장된 메시지가 없습니다.");
      return;
    }

    messages.forEach((msg) => {
      const role = msg.role === "user" ? "user" : "ai";

      const content =
        msg.content ||
        msg.message ||
        msg.text ||
        msg.answer ||
        "";

      addMessage(role, content);
    });
  } catch (error) {
    console.error(error);
    alert("대화 불러오기 중 오류가 발생했습니다.");
  }
}

/**
 * 처음 접속 시 기본 데이터 로드
 */
loadData();
loadConversations();
loadSummary();