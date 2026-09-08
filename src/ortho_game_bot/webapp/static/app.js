const tg = window.Telegram?.WebApp;
tg?.ready();
tg?.expand();
try { tg?.disableVerticalSwipes?.(); } catch (_) {}

const state = { user: null, question: null, pending: null, score: 0 };
const $ = (id) => document.getElementById(id);
const screens = ["loading", "grade-screen", "welcome-screen", "game-screen", "summary"];
const celebrationColors = ["#ffc83d", "#f7942d", "#26b96b", "#5aa9ff", "#e85d9b"];

function showScreen(id) {
  screens.forEach((screen) => $(screen).classList.toggle("hidden", screen !== id));
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": tg?.initData || "",
      ...(options.headers || {}),
    },
  });
  if (!response.ok) throw new Error((await response.text()) || "Не удалось загрузить игру");
  return response.json();
}

function toast(message) {
  $("error-toast").textContent = message;
  $("error-toast").classList.remove("hidden");
  setTimeout(() => $("error-toast").classList.add("hidden"), 3500);
}

function resetCelebration(container) {
  container.replaceChildren();
}

function celebrate(container, intense = false) {
  resetCelebration(container);
  const confettiCount = intense ? 34 : 22;
  const pieces = [];
  for (let index = 0; index < confettiCount; index += 1) {
    const piece = document.createElement("i");
    piece.className = "confetti";
    piece.style.setProperty("--x", `${4 + Math.random() * 92}%`);
    piece.style.setProperty("--delay", `${Math.random() * .3}s`);
    piece.style.setProperty("--duration", `${1.05 + Math.random() * .7}s`);
    piece.style.setProperty("--drift", `${-55 + Math.random() * 110}px`);
    piece.style.setProperty("--spin", `${260 + Math.random() * 520}deg`);
    piece.style.setProperty("--color", celebrationColors[index % celebrationColors.length]);
    pieces.push(piece);
  }
  const bursts = intense ? 3 : 2;
  for (let index = 0; index < bursts; index += 1) {
    const burst = document.createElement("i");
    burst.className = "firework";
    burst.style.setProperty("--x", `${22 + index * (56 / Math.max(1, bursts - 1))}%`);
    burst.style.setProperty("--y", `${18 + (index % 2) * 16}%`);
    burst.style.setProperty("--delay", `${.08 + index * .14}s`);
    burst.style.setProperty("--color", celebrationColors[(index + 1) % celebrationColors.length]);
    pieces.push(burst);
  }
  container.replaceChildren(...pieces);
}

function setCat(name, phrase, reaction = "reaction") {
  const stage = $("cat-stage");
  $("cat-image").src = `/static/assets/cat-${name}.webp`;
  $("cat-message").textContent = phrase;
  stage.classList.remove("reaction", "success", "wrong");
  void stage.offsetWidth;
  stage.classList.add(reaction);
}

function renderGrades() {
  $("grades").replaceChildren(...Array.from({ length: 11 }, (_, index) => {
    const grade = index + 1;
    const button = document.createElement("button");
    button.className = "grade-button";
    button.textContent = `${grade} класс`;
    button.addEventListener("click", () => chooseGrade(grade));
    return button;
  }));
}

async function chooseGrade(grade) {
  try {
    const data = await api("/api/profile/grade", {
      method: "POST", body: JSON.stringify({ grade }),
    });
    state.user = data.user;
    openWelcome();
  } catch (error) { toast(error.message); }
}

function openWelcome() {
  document.body.classList.toggle("junior", state.user.grade <= 2);
  $("welcome-score").textContent = `${state.user.total_score} ⭐`;
  $("welcome-copy").textContent = state.user.grade <= 2
    ? "Смотри на картинку и выбирай слово большими кнопками."
    : "10 слов — и ты станешь ещё грамотнее!";
  showScreen("welcome-screen");
}

async function startGame() {
  $("start-game").disabled = true;
  try {
    const data = await api("/api/game/start", { method: "POST", body: "{}" });
    state.question = data.question;
    state.score = 0;
    renderQuestion();
    showScreen("game-screen");
    tg?.HapticFeedback?.impactOccurred("medium");
  } catch (error) { toast(error.message); }
  finally { $("start-game").disabled = false; }
}

function renderQuestion() {
  const q = state.question;
  const number = q.position + 1;
  $("progress-label").textContent = `${number} из ${q.total}`;
  $("progress-fill").style.width = `${(number / q.total) * 100}%`;
  $("score-label").textContent = `${state.score} ⭐`;
  const visual = $("word-visual");
  visual.replaceChildren();
  if (q.visual.image) {
    const image = document.createElement("img");
    image.src = q.visual.image;
    image.alt = "Картинка-подсказка";
    image.addEventListener("error", () => { visual.textContent = q.visual.emoji; });
    visual.append(image);
  } else {
    visual.textContent = q.visual.emoji;
  }
  $("word-group").textContent = q.group;
  resetCelebration($("game-celebration"));
  setCat("idle", number === 1 ? "Смотри внимательно!" : "Какой вариант верный?");
  $("answers").replaceChildren(...q.options.map((option, index) => {
    const button = document.createElement("button");
    button.className = "answer-button";
    button.textContent = option;
    button.addEventListener("click", () => submitAnswer(index));
    return button;
  }));
}

async function submitAnswer(option) {
  document.querySelectorAll(".answer-button").forEach((button) => { button.disabled = true; });
  try {
    const q = state.question;
    const data = await api("/api/game/answer", {
      method: "POST",
      body: JSON.stringify({ session_id: q.session_id, position: q.position, option }),
    });
    state.pending = data;
    state.score = data.outcome.score_so_far;
    showFeedback(data.outcome);
  } catch (error) {
    toast(error.message);
    document.querySelectorAll(".answer-button").forEach((button) => { button.disabled = false; });
  }
}

function showFeedback(outcome) {
  const correct = outcome.is_correct;
  const streak = outcome.streak_after;
  const catState = correct ? (streak >= 3 ? "streak" : "correct") : "wrong";
  const card = $("feedback-card");
  card.classList.remove("is-correct", "is-streak", "is-wrong");
  void card.offsetWidth;
  card.classList.add(correct ? (streak >= 3 ? "is-streak" : "is-correct") : "is-wrong");
  $("feedback-cat").src = `/static/assets/cat-${catState}.webp`;
  $("feedback-title").textContent = correct ? (streak >= 3 ? `Серия ${streak}!` : "Верно!") : "Ой! Кот задумался";
  $("selected-answer").classList.toggle("hidden", correct);
  $("selected-answer").textContent = correct ? "" : `Было выбрано: ${outcome.selected_answer}`;
  $("correct-word").textContent = outcome.correct_answer;
  $("points-line").textContent = `${outcome.points >= 0 ? "+" : ""}${outcome.points} очков`;
  if (correct) celebrate($("feedback-celebration"), streak >= 3);
  else resetCelebration($("feedback-celebration"));
  $("feedback").classList.remove("hidden");
  tg?.HapticFeedback?.notificationOccurred(correct ? "success" : "warning");
}

function nextQuestion() {
  $("feedback").classList.add("hidden");
  resetCelebration($("feedback-celebration"));
  const data = state.pending;
  if (data.question) {
    state.question = data.question;
    renderQuestion();
    return;
  }
  const summary = data.summary;
  $("summary-correct").textContent = `${summary.correct_count}/${summary.questions_total}`;
  $("summary-streak").textContent = `${summary.best_streak} 🔥`;
  $("summary-score").textContent = `${summary.total_score} ⭐`;
  state.user.total_score = summary.total_score;
  showScreen("summary");
}

async function bootstrap() {
  renderGrades();
  try {
    const data = await api("/api/bootstrap");
    state.user = data.user;
    state.user.grade ? openWelcome() : showScreen("grade-screen");
  } catch (error) {
    showScreen("loading");
    toast("Откройте игру кнопкой внутри Telegram-бота.");
  }
}

$("start-game").addEventListener("click", startGame);
$("play-again").addEventListener("click", startGame);
$("next-question").addEventListener("click", nextQuestion);
$("close-game").addEventListener("click", () => tg?.close?.());
bootstrap();
