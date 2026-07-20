#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Задание 1. Экзамен.

Моделирование сдачи экзамена. Каждый экзаменатор работает в ОТДЕЛЬНОМ
ПРОЦЕССЕ (multiprocessing.Process). Студенты стоят в общей очереди; как
только экзаменатор освобождается, к нему заходит первый студент из очереди.

Общее состояние (списки студентов/экзаменаторов, очередь, статистика по
вопросам) живёт в multiprocessing.Manager и защищено одним Lock.
Главный процесс отвечает за «живой» вывод таблиц на месте (ANSI) и за
итоговую статистику.

Правила модели (см. постановку):
  * Вероятности выбора слова -- по закону золотого сечения (a=1/Ф,
    b=(1-a)/Ф, ...). Мальчики тяготеют к началу вопроса, девочки -- к концу.
  * Экзаменатор заранее ответа не знает и выбирает верные слова так же:
    первое -- по золотому сечению своего пола, каждое следующее --
    с вероятностью 1/3, пока не остановится или не выберет все слова.
  * Настроение: 1/8 -- провал, 1/4 -- сдан, 5/8 -- объективно
    (сдал, если верных ответов больше, чем неверных).
  * Длительность приёма -- случайное вещественное число из диапазона
    [len(name) - 1, len(name) + 1] (для «Степан» -> 5..7).
  * Спустя 30 c от начала экзамена экзаменатор имеет право на обед:
    закончив текущего студента, в течение случайного времени из [12, 18]
    секунд никого не принимает (один раз за экзамен).
"""

import os
import sys
import time
import random
import signal
from multiprocessing import Process, Manager, Lock

# --- Константы ---
PHI = (1 + 5 ** 0.5) / 2          # пропорция золотого сечения ~1.618
LUNCH_AFTER = 30.0                 # спустя сколько секунд можно уйти на обед
LUNCH_RANGE = (12.0, 18.0)         # длительность обеда
DUR_DELTA = 1                      # длительность приёма = uniform(len(name) ± DUR_DELTA)
MOOD_BAD = 1 / 8                   # плохое настроение -> провал
MOOD_GOOD = MOOD_BAD + 1 / 4       # граница хорошего настроения -> сдан

# Коды статусов студента.
S_QUEUE = 0                        # в очереди (или уже у экзаменатора)
S_PASSED = 1                       # сдал
S_FAILED = 2                       # провалил

# Файлы лежат рядом со скриптом.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_EXAMINERS = os.path.join(BASE_DIR, "examiners.txt")
DEFAULT_STUDENTS = os.path.join(BASE_DIR, "students.txt")
DEFAULT_QUESTIONS = os.path.join(BASE_DIR, "questions.txt")


# ---------------------------------------------------------------------------
# Чтение входных данных
# ---------------------------------------------------------------------------

def parse_person(line):
    """ 'Иван М' -> ('Иван', 'М'). """
    parts = line.split()
    if len(parts) != 2 or parts[1] not in ("М", "Ж"):
        raise ValueError("Некорректная строка: %r (ожидалось 'Имя М|Ж')" % line)
    return parts[0], parts[1]


def load_persons(path):
    with open(path, encoding="utf-8") as f:
        return [parse_person(line) for line in f if line.strip()]


def load_questions(path):
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


# ---------------------------------------------------------------------------
# Вероятностная модель
# ---------------------------------------------------------------------------

def golden_probs(n):
    """ Вероятности a, b, c, ... по закону золотого сечения для n слов.

    a = 1/Ф, b = (1-a)/Ф, c = (1-a-b)/Ф, ...; последнее слово забирает
    остаток, чтобы сумма вероятностей равнялась 1.
    """
    probs, rem = [], 1.0
    for i in range(n):
        if i == n - 1:
            probs.append(rem)
        else:
            p = rem / PHI
            probs.append(p)
            rem -= p
    return probs


def pick_index(n, gender):
    """ Индекс выбранного слова. Мальчики -- ближе к началу, девочки -- к концу. """
    probs = golden_probs(n)
    if gender == "Ж":
        probs = list(reversed(probs))
    r, cum = random.random(), 0.0
    for i, p in enumerate(probs):
        cum += p
        if r <= cum:
            return i
    return n - 1


def examiner_correct_indices(n, gender):
    """ Множество индексов верных ответов экзаменатора.

    Первое слово -- по золотому сечению своего пола. Затем с вероятностью
    1/3 добавляется ещё одно (равномерно из оставшихся), и так далее, пока
    экзаменатор не остановится или не выберет все слова вопроса.
    """
    correct = {pick_index(n, gender)}
    while len(correct) < n and random.random() < 1 / 3:
        remaining = [i for i in range(n) if i not in correct]
        correct.add(random.choice(remaining))
    return correct


def conduct(student_gender, examiner_gender, questions):
    """ Прогон одного студента по трём вопросам (берутся по порядку).

    Возвращает (сдал, список индексов вопросов, отвеченных верно).
    """
    k = min(3, len(questions))
    correct_n = wrong_n = 0
    correct_qi = []
    for qi in range(k):
        words = questions[qi].split()
        n = len(words)
        sw = pick_index(n, student_gender)
        cw = examiner_correct_indices(n, examiner_gender)
        if sw in cw:
            correct_n += 1
            correct_qi.append(qi)
        else:
            wrong_n += 1
    r = random.random()
    if r < MOOD_BAD:
        passed = False
    elif r < MOOD_GOOD:
        passed = True
    else:
        passed = correct_n > wrong_n
    return passed, correct_qi


# ---------------------------------------------------------------------------
# Конструкторы записей (хранятся в Manager-структурах)
# ---------------------------------------------------------------------------

def make_student(name, gender, idx):
    return {
        "name": name,
        "gender": gender,
        "idx": idx,                # позиция в изначальной очереди
        "status": S_QUEUE,
        "duration": 0.0,           # сколько длился приём (с)
        "finish_time": 0.0,        # момент завершения от начала экзамена
        "examiner": "",
    }


def make_examiner(name, gender, idx):
    return {
        "name": name,
        "gender": gender,
        "idx": idx,
        "current": "",             # имя текущего студента; "" -> "-"
        "total": 0,
        "failed": 0,
        "finished_at": 0.0,        # момент завершения работы (от начала)
    }


# ---------------------------------------------------------------------------
# Процесс-экзаменатор
# ---------------------------------------------------------------------------

def examiner_process(idx, examiners, students, queue, lock, qstats,
                     questions, start_ts):
    """ Рабочий цикл одного экзаменатора в отдельном процессе. """
    # Копия своего описания (читаем под локом).
    with lock:
        me = dict(examiners[idx])
    name, gender = me["name"], me["gender"]

    lo = max(0.1, len(name) - DUR_DELTA)
    hi = len(name) + DUR_DELTA
    lunched = False  # обедал ли уже в этом экзамене

    while True:
        # Берём первого студента из общей очереди.
        with lock:
            if not queue:
                # Очередь пуста -- экзаменатор завершает работу.
                me = dict(examiners[idx])
                me["current"] = ""
                me["finished_at"] = time.time() - start_ts
                examiners[idx] = me
                return
            order_idx = queue.pop(0)
            stu = dict(students[order_idx])
            # Отмечаем, что студент у данного экзаменатора.
            me = dict(examiners[idx])
            me["current"] = stu["name"]
            examiners[idx] = me

        # Длительность приёма (случайное вещественное число из диапазона).
        duration = random.uniform(lo, hi)
        time.sleep(duration)

        # Оценка студента (вычисления мгновенны, время моделировалось sleep).
        passed, correct_qi = conduct(stu["gender"], gender, questions)
        now = time.time() - start_ts

        with lock:
            stu["status"] = S_PASSED if passed else S_FAILED
            stu["duration"] = duration
            stu["finish_time"] = now
            stu["examiner"] = name
            students[order_idx] = stu

            me = dict(examiners[idx])
            me["total"] += 1
            if not passed:
                me["failed"] += 1
            me["current"] = ""
            examiners[idx] = me

            for qi in correct_qi:
                qstats[qi] = qstats.get(qi, 0) + 1

        # Обед: спустя 30 c от начала, один раз, если есть ещё студенты.
        if not lunched and now >= LUNCH_AFTER:
            lunched = True
            with lock:
                has_more = bool(queue)
            if has_more:
                time.sleep(random.uniform(*LUNCH_RANGE))


# ---------------------------------------------------------------------------
# Форматирование таблиц
# ---------------------------------------------------------------------------

def make_table(headers, rows, aligns):
    """ ASCII-таблица в стиле prettytable.

    aligns: 'l' -- текст/имя слева с отступом, 'c' -- по центру.
    """
    ncol = len(headers)
    widths = [len(h) for h in headers]
    for r in rows:
        for i in range(ncol):
            widths[i] = max(widths[i], len(str(r[i])))
    widths = [w + 2 for w in widths]   # по одному пробелу с каждой стороны

    def sep():
        return "+" + "+".join("-" * w for w in widths) + "+"

    def line(cells):
        out = []
        for i, c in enumerate(cells):
            s = str(c)
            if aligns[i] == "c":
                out.append(s.center(widths[i]))
            else:
                out.append(" " + s.ljust(widths[i] - 1))
        return "|" + "|".join(out) + "|"

    res = [sep(), line(headers), sep()]
    for r in rows:
        res.append(line(r))
    res.append(sep())
    return "\n".join(res)


STATUS_TEXT = {S_QUEUE: "Очередь", S_PASSED: "Сдал", S_FAILED: "Провалил"}
STATUS_RANK_LIVE = {S_QUEUE: 0, S_PASSED: 1, S_FAILED: 2}   # очередь -> сдавшие -> провалившие
STATUS_RANK_FINAL = {S_PASSED: 0, S_FAILED: 1}              # сдавшие -> провалившие


# ---------------------------------------------------------------------------
# Живой вывод (во время работы)
# ---------------------------------------------------------------------------

def build_live(snap_s, snap_e, q_left, total, procs_alive, now_from_start):
    """ Текст живого вывода по снепшотам состояния. """
    # Таблица студентов: очередь (по порядку), затем сдавшие, затем провалившие.
    ordered = sorted(snap_s, key=lambda s: (STATUS_RANK_LIVE[s["status"]], s["idx"]))
    student_rows = [[s["name"], STATUS_TEXT[s["status"]]] for s in ordered]
    student_tbl = make_table(["Студент", "Статус"], student_rows, ["l", "c"])

    # Таблица экзаменаторов.
    ex_rows = []
    for i, e in enumerate(snap_e):
        cur = e["current"] if e["current"] else "-"
        if procs_alive[i]:
            wt = now_from_start
        else:
            wt = e["finished_at"] if e["finished_at"] else now_from_start
        ex_rows.append([e["name"], cur, e["total"], e["failed"], "%.2f" % wt])
    examiner_tbl = make_table(
        ["Экзаменатор", "Текущий студент", "Всего студентов",
         "Завалил", "Время работы"],
        ex_rows, ["l", "c", "c", "c", "c"])

    lines = [student_tbl, "", examiner_tbl, "",
             "Осталось в очереди: %d из %d" % (q_left, total),
             "Время с момента начала экзамена: %.2f" % now_from_start]
    return "\n".join(lines)


def render_inplace(text, prev_lines):
    """ Перерисовывает блок текста на месте с помощью ANSI-кодов. """
    if prev_lines > 0:
        sys.stdout.write("\033[%dA" % prev_lines)   # вверх на prev_lines строк
        sys.stdout.write("\033[J")                  # очистить от курсора до конца
    sys.stdout.write(text + "\n")
    sys.stdout.flush()
    return text.count("\n") + 1


# ---------------------------------------------------------------------------
# Итоговый вывод (после работы)
# ---------------------------------------------------------------------------

def build_final(snap_s, snap_e, snap_q, questions, total_elapsed):
    """ Итоговые таблицы и вся статистика. """
    passed = [s for s in snap_s if s["status"] == S_PASSED]
    failed = [s for s in snap_s if s["status"] == S_FAILED]

    # Таблица студентов: сдавшие, затем провалившие.
    rows = [[s["name"], "Сдал"] for s in sorted(passed, key=lambda s: s["idx"])]
    rows += [[s["name"], "Провалил"] for s in sorted(failed, key=lambda s: s["idx"])]
    student_tbl = make_table(["Студент", "Статус"], rows, ["l", "c"])

    # Таблица экзаменаторов.
    ex_rows = []
    for e in snap_e:
        wt = e["finished_at"] if e["finished_at"] else 0.0
        ex_rows.append([e["name"], e["total"], e["failed"], "%.2f" % wt])
    examiner_tbl = make_table(
        ["Экзаменатор", "Всего студентов", "Завалил", "Время работы"],
        ex_rows, ["l", "c", "c", "c"])

    # Лучшие студенты: быстрее других сдали (минимальное время завершения).
    if passed:
        best_t = min(s["finish_time"] for s in passed)
        best_students = [s["name"] for s in sorted(passed, key=lambda s: s["idx"])
                         if s["finish_time"] == best_t]
    else:
        best_students = []

    # Лучшие экзаменаторы: минимальный процент завала (среди принимавших).
    active = [e for e in snap_e if e["total"] > 0]
    if active:
        best_rate = min(e["failed"] / e["total"] for e in active)
        best_examiners = [e["name"] for e in sorted(active, key=lambda e: e["idx"])
                          if e["failed"] / e["total"] == best_rate]
    else:
        best_examiners = []

    # Отчисление: провалившие, закончившие раньше других проваливших.
    if failed:
        worst_t = min(s["finish_time"] for s in failed)
        expelled = [s["name"] for s in sorted(failed, key=lambda s: s["idx"])
                    if s["finish_time"] == worst_t]
    else:
        expelled = []

    # Лучшие вопросы: на них верно ответило больше всего студентов.
    if snap_q:
        best_c = max(snap_q.values())
        best_questions = [questions[qi] for qi in sorted(snap_q)
                          if snap_q[qi] == best_c]
    else:
        best_questions = []

    # Удался ли экзамен: сдало больше 85%.
    total = len(snap_s)
    ratio = (len(passed) / total) if total else 0.0
    success = ratio > 0.85

    def joined(lst):
        return ", ".join(lst) if lst else "-"

    lines = [
        student_tbl, "", examiner_tbl, "",
        "Время с момента начала экзамена и до момента его завершения: %.2f"
        % total_elapsed,
        "Имена лучших студентов: %s" % joined(best_students),
        "Имена лучших экзаменаторов: %s" % joined(best_examiners),
        "Имена студентов, которых после экзамена отчислят: %s" % joined(expelled),
        "Лучшие вопросы: %s" % joined(best_questions),
        "Вывод: " + ("экзамен удался" if success else "экзамен не удался"),
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Главный процесс
# ---------------------------------------------------------------------------

def main():
    ex_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EXAMINERS
    stu_file = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_STUDENTS
    q_file = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_QUESTIONS

    ex_data = load_persons(ex_file)
    stu_data = load_persons(stu_file)
    questions = load_questions(q_file)

    if not ex_data:
        print("Нет экзаменаторов."); return
    if not stu_data:
        print("Нет студентов."); return
    if not questions:
        print("Нет вопросов."); return

    manager = Manager()
    lock = Lock()

    # Общее состояние в Manager.
    examiners = manager.list(
        [make_examiner(n, g, i) for i, (n, g) in enumerate(ex_data)])
    students = manager.list(
        [make_student(n, g, i) for i, (n, g) in enumerate(stu_data)])
    queue = manager.list(range(len(stu_data)))   # порядок файла = порядок очереди
    qstats = manager.dict()

    start_ts = time.time()

    # По процессу на каждого экзаменатора.
    procs = []
    for i in range(len(ex_data)):
        p = Process(target=examiner_process,
                    args=(i, examiners, students, queue, lock, qstats,
                          questions, start_ts))
        procs.append(p)

    # Корректное завершение по Ctrl-C.
    def on_sigint(sig, frame):
        for p in procs:
            if p.is_alive():
                p.terminate()
        sys.stdout.write("\nПрервано пользователем.\n")
        sys.stdout.flush()
        sys.exit(1)

    try:
        signal.signal(signal.SIGINT, on_sigint)
    except (ValueError, OSError):
        pass  # signal handler можно ставить только в главном потоке

    for p in procs:
        p.start()

    # Живой вывод, пока жив хотя бы один процесс-экзаменатор.
    prev_lines = 0
    total_students = len(stu_data)
    try:
        while any(p.is_alive() for p in procs):
            now_from_start = time.time() - start_ts
            with lock:
                snap_s = [dict(s) for s in students]
                snap_e = [dict(e) for e in examiners]
                q_left = len(queue)
            procs_alive = [p.is_alive() for p in procs]
            out = build_live(snap_s, snap_e, q_left, total_students,
                             procs_alive, now_from_start)
            prev_lines = render_inplace(out, prev_lines)
            time.sleep(0.1)
    finally:
        for p in procs:
            p.join()

    # Все экзаменаторы завершились -- снимаем финальное состояние.
    time.sleep(0.05)
    with lock:
        snap_s = [dict(s) for s in students]
        snap_e = [dict(e) for e in examiners]
        snap_q = dict(qstats)

    total_elapsed = time.time() - start_ts

    # Стираем блок живого вывода и печатаем итоговый отчёт.
    if prev_lines > 0:
        sys.stdout.write("\033[%dA" % prev_lines)
        sys.stdout.write("\033[J")
    final = build_final(snap_s, snap_e, snap_q, questions, total_elapsed)
    sys.stdout.write(final + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
