const tg = window.Telegram?.WebApp;
tg?.ready();
tg?.expand();
try { tg?.disableVerticalSwipes?.(); } catch (_) {}

const state = {
  user: null,
  question: null,
  pending: null,
  score: 0,
  library: {
    catalog: null,
    book: null,
    progress: null,
    step: null,
    phase: "story",
    pending: null,
    reviews: [],
    reviewIndex: 0,
  },
  art: {
    ageMode: "teen",
    language: "ru",
    catalog: null,
    session: null,
    question: null,
    pending: null,
    diagnostic: null,
  },
};
const $ = (id) => document.getElementById(id);
const screens = [
  "loading", "grade-screen", "welcome-screen", "library-screen",
  "library-mission-screen", "library-question-screen", "library-summary",
  "art-screen", "art-question-screen", "art-summary", "art-diagnostic",
  "game-screen", "summary",
];
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
  $("welcome-copy").textContent = "Выбери своё приключение с Котом Учёным";
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

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function openLibrary() {
  try {
    const [catalog, reviewData] = await Promise.all([
      api("/api/library/books"),
      api("/api/library/reviews"),
    ]);
    state.library.catalog = catalog;
    state.library.reviews = reviewData.reviews;
    $("library-counter").textContent = `${catalog.completed_count}/${catalog.total_count}`;
    $("review-count").textContent = `${reviewData.reviews.length} ${reviewData.reviews.length === 1 ? "задание" : "задания"} для памяти`;
    $("open-reviews").classList.toggle("hidden", reviewData.reviews.length === 0);
    renderLibraryCatalog(catalog.books);
    showScreen("library-screen");
  } catch (error) { toast(error.message); }
}

function renderLibraryCatalog(books) {
  $("library-books").replaceChildren(...books.map((book) => {
    const button = document.createElement("button");
    const completed = book.status === "completed";
    const active = book.status === "active";
    button.className = `book-card ${completed ? "is-complete" : ""} ${!book.unlocked ? "is-locked" : ""}`;
    button.disabled = !book.unlocked;
    const status = completed ? "Пройдено ✓" : active ? `${book.current_step}/8` : book.unlocked ? "Начать" : "Закрыто";
    button.innerHTML = `
      <span class="book-number">${escapeHtml(book.book_id)}</span>
      <span class="book-copy"><b>${escapeHtml(book.title)}</b><small>${escapeHtml(book.author)}</small><em>${escapeHtml(book.mission_title)}</em></span>
      <span class="book-status">${status}</span>`;
    if (book.unlocked) button.addEventListener("click", () => startLibraryBook(book.book_id));
    return button;
  }));
}

async function startLibraryBook(bookId) {
  try {
    const data = await api(`/api/library/books/${bookId}/start`, { method: "POST", body: "{}" });
    state.library.book = data.book;
    state.library.progress = data.progress;
    state.library.step = data.step || null;
    state.library.phase = data.progress.current_step === 0 && data.progress.answers_count === 0 ? "hook" : "story";
    if (data.progress.status === "completed") showLibrarySummary(data.summary);
    else showLibraryStory();
    tg?.HapticFeedback?.impactOccurred("light");
  } catch (error) { toast(error.message); }
}

function setLibraryProgress(prefix) {
  const progress = state.library.progress;
  const current = Math.min(progress.current_step + 1, progress.step_total);
  $(`${prefix}-progress-label`).textContent = `${prefix === "mission" ? "Эпизод" : "Вопрос"} ${current} из ${progress.step_total}`;
  $(`${prefix}-score`).textContent = `${progress.first_attempt_correct}/${progress.step_total}`;
  $(`${prefix}-progress-fill`).style.width = `${(progress.current_step / progress.step_total) * 100}%`;
}

function showLibraryStory() {
  const lib = state.library;
  setLibraryProgress("mission");
  $("mission-book-number").textContent = `Книга ${lib.book.book_id}`;
  $("mission-book-title").textContent = lib.book.title;
  if (lib.phase === "hook") {
    $("story-eyebrow").textContent = "Вводная история";
    $("story-title").textContent = lib.book.mission_title;
    $("story-text").textContent = lib.book.hook;
    $("library-to-question").textContent = "Начать миссию";
    $("mission-cat").src = "/static/assets/cat-welcome.webp";
  } else {
    $("story-eyebrow").textContent = lib.step.eyebrow;
    $("story-title").textContent = lib.step.title;
    $("story-text").textContent = lib.step.text;
    $("library-to-question").textContent = "К вопросу";
    $("mission-cat").src = "/static/assets/cat-idle.webp";
  }
  showScreen("library-mission-screen");
}

function libraryToQuestion() {
  if (state.library.phase === "hook") {
    state.library.phase = "story";
    showLibraryStory();
    return;
  }
  renderLibraryQuestion(state.library.step.question);
}

function questionKindLabel(type) {
  return ({
    main_idea: "Понимаю",
    application: "Применяю",
    inference: "Делаю вывод",
    critical_thinking: "Проверяю идею",
  })[type] || "Принимаю решение";
}

function renderLibraryQuestion(question, review = false) {
  state.library.phase = review ? "review" : "question";
  if (review) {
    const item = state.library.reviews[state.library.reviewIndex];
    $("question-progress-label").textContent = `Повторение ${state.library.reviewIndex + 1} из ${state.library.reviews.length}`;
    $("question-score").textContent = item.review_kind === "24h" ? "24 ч" : "7 дней";
    $("question-progress-fill").style.width = `${((state.library.reviewIndex + 1) / state.library.reviews.length) * 100}%`;
  } else {
    setLibraryProgress("question");
  }
  $("question-kind").textContent = review ? "Закрепляю" : questionKindLabel(question.type);
  $("library-question-prompt").textContent = question.prompt;
  $("question-cat-message").textContent = review ? "Вспомни идею книги" : "Выбери самый точный ответ";
  $("question-cat").src = "/static/assets/cat-hint.webp";
  const totalLength = question.options.reduce((sum, option) => sum + option.length, 0);
  $("library-answers").classList.toggle("dense", totalLength > 270);
  $("library-answers").replaceChildren(...question.options.map((option, index) => {
    const button = document.createElement("button");
    button.className = "library-answer-button";
    button.innerHTML = `<span>${String.fromCharCode(65 + index)}</span><b>${escapeHtml(option)}</b>`;
    button.addEventListener("click", () => submitLibraryAnswer(index));
    return button;
  }));
  showScreen("library-question-screen");
}

async function submitLibraryAnswer(option) {
  document.querySelectorAll(".library-answer-button").forEach((button) => { button.disabled = true; });
  const lib = state.library;
  try {
    const isReview = lib.phase === "review";
    const body = isReview
      ? { book_id: lib.reviews[lib.reviewIndex].book_id, review_kind: lib.reviews[lib.reviewIndex].review_kind, option }
      : { book_id: lib.book.book_id, step_index: lib.step.step_index, option };
    const data = await api(isReview ? "/api/library/reviews/answer" : "/api/library/answer", {
      method: "POST", body: JSON.stringify(body),
    });
    lib.pending = { ...data, isReview, selectedText: (isReview ? lib.reviews[lib.reviewIndex].question : lib.step.question).options[option] };
    showLibraryFeedback(lib.pending);
  } catch (error) {
    toast(error.message);
    document.querySelectorAll(".library-answer-button").forEach((button) => { button.disabled = false; });
  }
}

function showLibraryFeedback(result) {
  const retry = result.allow_retry === true;
  const correct = result.is_correct;
  const card = $("library-feedback-card");
  card.classList.remove("is-correct", "is-wrong");
  card.classList.add(correct ? "is-correct" : "is-wrong");
  $("library-feedback-cat").src = `/static/assets/cat-${correct ? "correct" : retry ? "hint" : "support"}.webp`;
  $("library-feedback-title").textContent = correct ? "Верно!" : retry ? "Почти. Проверь ещё раз" : "Разберём решение";
  $("library-selected-answer").classList.toggle("hidden", correct);
  $("library-selected-answer").textContent = correct ? "" : `Твой ответ: ${result.selectedText}`;
  $("library-correct-wrap").classList.toggle("hidden", retry);
  $("library-correct-answer").textContent = retry ? "" : result.correct_answer;
  $("library-explanation").textContent = retry ? result.hint : result.explanation;
  $("library-points").textContent = retry ? "Используй подсказку — у тебя есть вторая попытка" : result.points ? "+10 очков" : "Идея добавлена в память";
  $("library-feedback-next").textContent = retry ? "Попробовать ещё раз" : result.mission_completed ? "Итоги миссии" : "Продолжить";
  if (correct) celebrate($("library-feedback-celebration"), result.mission_completed);
  else resetCelebration($("library-feedback-celebration"));
  $("library-feedback").classList.remove("hidden");
  tg?.HapticFeedback?.notificationOccurred(correct ? "success" : "warning");
}

function nextLibraryStep() {
  const result = state.library.pending;
  $("library-feedback").classList.add("hidden");
  resetCelebration($("library-feedback-celebration"));
  if (result.allow_retry) {
    renderLibraryQuestion(state.library.step.question);
    return;
  }
  if (result.isReview) {
    state.library.reviewIndex += 1;
    if (state.library.reviewIndex < state.library.reviews.length) {
      renderLibraryQuestion(state.library.reviews[state.library.reviewIndex].question, true);
    } else {
      openLibrary();
    }
    return;
  }
  state.library.progress.first_attempt_correct = result.first_attempt_correct;
  state.library.progress.current_step += 1;
  if (Number.isInteger(result.total_score)) state.user.total_score = result.total_score;
  if (result.mission_completed) {
    state.library.progress.status = "completed";
    showLibrarySummary(result.summary);
    return;
  }
  state.library.step = result.next_step;
  state.library.phase = "story";
  showLibraryStory();
}

function showLibrarySummary(summary) {
  $("library-summary-title").textContent = `${summary.title} — пройдено!`;
  $("library-summary-score").textContent = `${summary.first_attempt_correct}/${summary.step_total}`;
  $("library-action").textContent = summary.action_24h;
  showScreen("library-summary");
}

function openReviews() {
  if (!state.library.reviews.length) return;
  state.library.reviewIndex = 0;
  renderLibraryQuestion(state.library.reviews[0].question, true);
}

const artCopy = {
  ru: {
    ages: { child: "7–11 лет", teen: "12–15 лет", adult: "16+ / взрослые" },
    title: "Мировое искусство",
    heroTitle: "Учитесь видеть, сравнивать и объяснять",
    heroCopy: "15 заданий в каждом разделе. Прогресс сохраняется автоматически.",
    diagnostic: "Моя культурная диагностика",
    diagnosticCopy: "Сильные темы и следующий шаг",
    start: "Начать",
    continue: "Продолжить",
    repeat: "Повторить",
    mastered: "Освоено",
    correct: "Верно!",
    wrong: "Разберём вместе",
    correctAnswer: "Правильный ответ",
    next: "Продолжить",
    completed: "Раздел завершён",
    diagnosticTitle: "Итоговая диагностика",
    diagnosticProgress: "разделов освоено",
    focus: "На чём сосредоточиться",
    map: "Карта культурной грамотности",
    note: "Диагностика отражает освоение учебного банка. Культурная грамотность также развивается через знакомство с оригиналами, чтение и обсуждение.",
    levels: { "1_FOUNDATION": "Понятия", "2_VISUAL": "Визуальное различение", "3_ANALYSIS": "Анализ" },
    bands: { not_started: "Старт", foundation: "Базовый уровень", developing: "Развивающийся уровень", confident: "Уверенный уровень", mastery: "Целостное освоение" },
    verdictMastered: "Порог освоения достигнут",
    verdictLearning: "Есть темы для укрепления",
    points: (value) => value ? `+${value} к общему счёту` : "Ответ сохранён",
    result: "Результат",
    enlarge: "Увеличить",
  },
  en: {
    ages: { child: "Ages 7–11", teen: "Ages 12–15", adult: "16+ / adults" },
    title: "World Art",
    heroTitle: "Learn to observe, compare and explain",
    heroCopy: "15 tasks in each module. Progress is saved automatically.",
    diagnostic: "My cultural literacy diagnostic",
    diagnosticCopy: "Strengths and the next learning step",
    start: "Start",
    continue: "Continue",
    repeat: "Retake",
    mastered: "Mastered",
    correct: "Correct!",
    wrong: "Let’s examine it",
    correctAnswer: "Correct answer",
    next: "Continue",
    completed: "Module completed",
    diagnosticTitle: "Final diagnostic",
    diagnosticProgress: "modules mastered",
    focus: "Where to focus next",
    map: "Cultural literacy map",
    note: "This diagnostic reflects mastery of the learning bank. Cultural literacy also grows through direct encounters with art, reading and discussion.",
    levels: { "1_FOUNDATION": "Concepts", "2_VISUAL": "Visual recognition", "3_ANALYSIS": "Analysis" },
    bands: { not_started: "Start", foundation: "Foundation", developing: "Developing", confident: "Confident", mastery: "Integrated mastery" },
    verdictMastered: "Mastery threshold reached",
    verdictLearning: "Some areas need strengthening",
    points: (value) => value ? `+${value} to your score` : "Answer saved",
    result: "Result",
    enlarge: "Enlarge",
  },
  kz: {
    ages: { child: "7–11 жас", teen: "12–15 жас", adult: "16+ / ересектер" },
    title: "Әлем өнері",
    heroTitle: "Көруді, салыстыруды және түсіндіруді үйреніңіз",
    heroCopy: "Әр бөлімде 15 тапсырма. Ілгерілеу автоматты түрде сақталады.",
    diagnostic: "Менің мәдени диагностикам",
    diagnosticCopy: "Күшті тақырыптар және келесі қадам",
    start: "Бастау",
    continue: "Жалғастыру",
    repeat: "Қайталау",
    mastered: "Меңгерілді",
    correct: "Дұрыс!",
    wrong: "Бірге талдайық",
    correctAnswer: "Дұрыс жауап",
    next: "Жалғастыру",
    completed: "Бөлім аяқталды",
    diagnosticTitle: "Қорытынды диагностика",
    diagnosticProgress: "бөлім меңгерілді",
    focus: "Неге назар аудару керек",
    map: "Мәдени сауаттылық картасы",
    note: "Диагностика оқу қорының меңгерілуін көрсетеді. Мәдени сауаттылық түпнұсқалармен танысу, оқу және талқылау арқылы да дамиды.",
    levels: { "1_FOUNDATION": "Ұғымдар", "2_VISUAL": "Көрнекі ажырату", "3_ANALYSIS": "Талдау" },
    bands: { not_started: "Бастау", foundation: "Базалық деңгей", developing: "Даму деңгейі", confident: "Сенімді деңгей", mastery: "Тұтас меңгеру" },
    verdictMastered: "Меңгеру шегіне жетті",
    verdictLearning: "Кей тақырыптарды нығайту керек",
    points: (value) => value ? `Жалпы ұпайға +${value}` : "Жауап сақталды",
    result: "Нәтиже",
    enlarge: "Үлкейту",
  },
};

function artText() {
  return artCopy[state.art.language];
}

function renderArtControls() {
  const copy = artText();
  $("art-age-modes").replaceChildren(...Object.entries(copy.ages).map(([mode, label]) => {
    const button = document.createElement("button");
    button.textContent = label;
    button.classList.toggle("is-active", state.art.ageMode === mode);
    button.addEventListener("click", () => {
      if (state.art.ageMode === mode) return;
      state.art.ageMode = mode;
      loadArtCatalog();
    });
    return button;
  }));
  $("art-languages").replaceChildren(...["ru", "en", "kz"].map((language) => {
    const button = document.createElement("button");
    button.textContent = language.toUpperCase();
    button.classList.toggle("is-active", state.art.language === language);
    button.addEventListener("click", () => {
      if (state.art.language === language) return;
      state.art.language = language;
      loadArtCatalog();
    });
    return button;
  }));
  document.body.classList.toggle("art-child", state.art.ageMode === "child");
}

function applyArtCopy() {
  const copy = artText();
  $("art-title").textContent = copy.title;
  $("art-hero-title").textContent = copy.heroTitle;
  $("art-hero-copy").textContent = copy.heroCopy;
  $("diagnostic-banner-title").textContent = copy.diagnostic;
  $("diagnostic-banner-copy").textContent = copy.diagnosticCopy;
  $("art-correct-label").textContent = copy.correctAnswer;
  $("art-feedback-next").textContent = copy.next;
  $("art-summary-kicker").textContent = copy.completed;
  $("art-summary-diagnostic").textContent = copy.diagnostic;
  $("art-summary-back").textContent = copy.continue;
  $("art-diagnostic-title").textContent = copy.diagnosticTitle;
  $("diagnostic-progress-copy").textContent = copy.diagnosticProgress;
  $("diagnostic-focus-title").textContent = copy.focus;
  $("diagnostic-map-title").textContent = copy.map;
  $("diagnostic-note").textContent = copy.note;
  $("art-enlarge-label").textContent = copy.enlarge;
}

async function openArt() {
  if (!state.art.catalog && state.user?.grade) {
    state.art.ageMode = state.user.grade <= 5 ? "child" : state.user.grade <= 9 ? "teen" : "adult";
  }
  await loadArtCatalog();
}

async function loadArtCatalog() {
  renderArtControls();
  applyArtCopy();
  try {
    const catalog = await api(`/api/art/modules?age_mode=${state.art.ageMode}&lang=${state.art.language}`);
    state.art.catalog = catalog;
    $("art-counter").textContent = `${catalog.mastered_count}/${catalog.total_count}`;
    renderArtModules(catalog.modules);
    showScreen("art-screen");
  } catch (error) { toast(error.message); }
}

function renderArtModules(modules) {
  const copy = artText();
  $("art-modules").replaceChildren(...modules.map((module) => {
    const button = document.createElement("button");
    const mastered = module.best?.mastered === true;
    button.className = `art-module-card ${mastered ? "is-mastered" : ""}`;
    let status = copy.start;
    if (module.progress?.status === "active") status = `${module.progress.current}/${module.progress.total}`;
    else if (mastered) status = `${copy.mastered} ✓`;
    else if (module.best) status = `${module.best.overall_percent}%`;
    button.innerHTML = `
      <span class="art-module-number">${escapeHtml(module.id)}</span>
      <span class="art-module-copy"><b>${escapeHtml(module.title)}</b><small>${escapeHtml(module.goal)}</small></span>
      <span class="art-module-status">${escapeHtml(status)}</span>`;
    button.addEventListener("click", () => startArtModule(module.id));
    return button;
  }));
}

async function startArtModule(moduleId) {
  try {
    const data = await api(`/api/art/modules/${moduleId}/start`, {
      method: "POST",
      body: JSON.stringify({ age_mode: state.art.ageMode, lang: state.art.language }),
    });
    state.art.session = data.session;
    state.art.question = data.question || null;
    if (data.summary) showArtSummary(data.summary);
    else renderArtQuestion();
    tg?.HapticFeedback?.impactOccurred("light");
  } catch (error) { toast(error.message); }
}

function renderArtQuestion() {
  const q = state.art.question;
  const session = state.art.session;
  const copy = artText();
  $("art-progress-label").textContent = `${q.position + 1} / ${q.total}`;
  $("art-score-label").textContent = `${session.correct_count} ✓`;
  $("art-progress-fill").style.width = `${(q.position / q.total) * 100}%`;
  $("art-question-module").textContent = `${q.module_id} · ${session.module.title}`;
  $("art-question-level").textContent = copy.levels[q.level];
  $("art-question-prompt").textContent = q.prompt;
  const visualButton = $("art-visual-button");
  visualButton.classList.toggle("hidden", !q.visual);
  if (q.visual) {
    $("art-main-image").src = q.visual.image;
    $("art-main-image").alt = q.visual.alt;
  }
  const layout = $("art-question-screen");
  layout.classList.toggle("is-visual-options", q.format === "VISUAL_4_OPTIONS");
  layout.classList.toggle("is-text-question", q.format !== "VISUAL_4_OPTIONS");
  $("art-answers").replaceChildren(...q.options.map((option, index) => {
    const button = document.createElement("button");
    button.className = `art-answer-button ${option.image ? "has-image" : ""}`;
    if (option.image) {
      const image = document.createElement("img");
      image.src = option.image;
      image.alt = option.alt || option.text;
      button.append(image);
    }
    const label = document.createElement("b");
    label.textContent = option.image ? String.fromCharCode(65 + index) : `${String.fromCharCode(65 + index)}. ${option.text}`;
    button.append(label);
    button.addEventListener("click", () => submitArtAnswer(option.id));
    return button;
  }));
  showScreen("art-question-screen");
}

async function submitArtAnswer(optionId) {
  document.querySelectorAll(".art-answer-button").forEach((button) => { button.disabled = true; });
  try {
    const data = await api("/api/art/answer", {
      method: "POST",
      body: JSON.stringify({
        session_id: state.art.session.id,
        question_id: state.art.question.id,
        option_id: optionId,
      }),
    });
    state.art.pending = data;
    showArtFeedback(data);
  } catch (error) {
    toast(error.message);
    document.querySelectorAll(".art-answer-button").forEach((button) => { button.disabled = false; });
  }
}

function showArtFeedback(result) {
  const copy = artText();
  const card = $("art-feedback-card");
  card.classList.remove("is-correct", "is-wrong");
  card.classList.add(result.is_correct ? "is-correct" : "is-wrong");
  $("art-feedback-cat").src = `/static/assets/cat-${result.is_correct ? "correct" : "support"}.webp`;
  $("art-feedback-title").textContent = result.is_correct ? copy.correct : copy.wrong;
  $("art-correct-answer").textContent = result.correct_answer;
  $("art-explanation").textContent = result.explanation;
  $("art-points").textContent = copy.points(result.points);
  $("art-feedback").classList.remove("hidden");
  tg?.HapticFeedback?.notificationOccurred(result.is_correct ? "success" : "warning");
}

function nextArtQuestion() {
  const result = state.art.pending;
  $("art-feedback").classList.add("hidden");
  if (Number.isInteger(result.total_score)) state.user.total_score = result.total_score;
  state.art.session.correct_count = result.correct_count;
  if (result.finished) {
    showArtSummary(result.summary);
    return;
  }
  state.art.session.position = result.position;
  state.art.question = result.next_question;
  renderArtQuestion();
}

function showArtSummary(summary) {
  const copy = artText();
  $("art-summary-title").textContent = `${state.art.session?.module?.title || copy.result}`;
  $("art-summary-percent").textContent = `${summary.overall_percent}%`;
  $("art-summary-verdict").textContent = summary.mastered ? copy.verdictMastered : copy.verdictLearning;
  $("art-summary-cat").src = `/static/assets/cat-${summary.mastered ? "winner" : "support"}.webp`;
  $("art-level-results").replaceChildren(...Object.entries(summary.level_scores).map(([level, score]) => {
    const row = document.createElement("div");
    const levelKey = { foundation: "1_FOUNDATION", visual: "2_VISUAL", analysis: "3_ANALYSIS" }[level];
    row.className = "level-result";
    row.innerHTML = `<span>${escapeHtml(copy.levels[levelKey])}</span><b>${score.correct}/${score.total} · ${score.percent}%</b><div class="level-result-track"><i style="width:${score.percent}%"></i></div>`;
    return row;
  }));
  showScreen("art-summary");
}

async function openArtDiagnostic() {
  applyArtCopy();
  try {
    const data = await api(`/api/art/diagnostic?age_mode=${state.art.ageMode}&lang=${state.art.language}`);
    state.art.diagnostic = data;
    renderArtDiagnostic(data);
    showScreen("art-diagnostic");
  } catch (error) { toast(error.message); }
}

function renderArtDiagnostic(data) {
  const copy = artText();
  $("diagnostic-overall").textContent = `${data.overall_percent}%`;
  $("diagnostic-band").textContent = copy.bands[data.band];
  $("diagnostic-progress").textContent = `${data.mastered_count} / ${data.total_count}`;
  $("diagnostic-focus").replaceChildren(...data.focus_modules.map((module) => {
    const card = document.createElement("button");
    card.className = "focus-card";
    card.innerHTML = `<span>${escapeHtml(module.id)}</span><b>${escapeHtml(module.title)}</b><em>${module.result ? `${module.result.overall_percent}%` : copy.start}</em>`;
    card.addEventListener("click", () => startArtModule(module.id));
    return card;
  }));
  $("diagnostic-map").replaceChildren(...data.modules.map((module) => {
    const cell = document.createElement("button");
    const result = module.result;
    cell.className = `diagnostic-cell ${result?.mastered ? "is-mastered" : result ? "is-focus" : ""}`;
    cell.innerHTML = `<b>${escapeHtml(module.id)}</b><span>${result ? `${result.overall_percent}%` : "—"}</span>`;
    cell.title = module.title;
    cell.addEventListener("click", () => startArtModule(module.id));
    return cell;
  }));
}

function openArtImage() {
  if (!state.art.question?.visual) return;
  $("art-dialog-image").src = state.art.question.visual.image;
  $("art-dialog-image").alt = state.art.question.visual.alt;
  $("art-image-dialog").showModal();
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
$("open-library").addEventListener("click", openLibrary);
$("open-art").addEventListener("click", openArt);
$("art-home").addEventListener("click", openWelcome);
$("art-question-back").addEventListener("click", loadArtCatalog);
$("open-art-diagnostic").addEventListener("click", openArtDiagnostic);
$("art-feedback-next").addEventListener("click", nextArtQuestion);
$("art-summary-diagnostic").addEventListener("click", openArtDiagnostic);
$("art-summary-back").addEventListener("click", loadArtCatalog);
$("art-diagnostic-back").addEventListener("click", loadArtCatalog);
$("art-visual-button").addEventListener("click", openArtImage);
$("art-image-close").addEventListener("click", () => $("art-image-dialog").close());
$("library-home").addEventListener("click", openWelcome);
$("mission-back").addEventListener("click", openLibrary);
$("question-back").addEventListener("click", () => state.library.phase === "review" ? openLibrary() : showLibraryStory());
$("library-to-question").addEventListener("click", libraryToQuestion);
$("library-feedback-next").addEventListener("click", nextLibraryStep);
$("library-summary-back").addEventListener("click", openLibrary);
$("open-reviews").addEventListener("click", openReviews);
$("play-again").addEventListener("click", startGame);
$("next-question").addEventListener("click", nextQuestion);
$("close-game").addEventListener("click", () => tg?.close?.());
bootstrap();
