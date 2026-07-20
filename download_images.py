# -*- coding: utf-8 -*-
"""
Задание 2. Скачивание изображений.
Асинхронный обработчик ссылок: пользователь вводит путь для сохранения,
затем последовательно вводит ссылки (по одной), скрипт асинхронно скачивает
изображения. Завершение по пустой строке — программа ждёт окончания всех
загрузок и выводит сводку.
"""
import os
import sys
import asyncio
from pathlib import Path

import aiohttp


# --- Путь сохранения ---
def prompt_save_dir():
    """Просит путь и проверяет возможность записи. Переспрашивает при ошибке."""
    while True:
        path = input("Введите путь для сохранения изображений: ").strip()
        if not path:
            print("Путь не может быть пустым.")
            continue
        try:
            p = Path(path)
            p.mkdir(parents=True, exist_ok=True)
            # проверка права на запись: создаём и удаляем тестовый файл
            probe = p / f".write_probe_{os.getpid()}.tmp"
            with open(probe, "w"):
                pass
            probe.unlink()
            return p
        except (OSError, PermissionError) as e:
            print(f"Некорректный путь или нет доступа для записи: {e}")
            print("Попробуйте другой путь.")


# --- Имя файла из ссылки ---
def filename_from_url(url):
    name = url.rstrip("/").rsplit("/", 1)[-1]
    # отрезаем query/fragment
    for sep in ("?", "#"):
        if sep in name:
            name = name.split(sep, 1)[0]
    if not name:
        name = "image"
    return name


def unique_path(save_dir, name):
    """Если файл существует — добавляет суффикс _1, _2, ..."""
    candidate = save_dir / name
    if not candidate.exists():
        return candidate
    stem, ext = candidate.stem, candidate.suffix
    i = 1
    while True:
        candidate = save_dir / f"{stem}_{i}{ext}"
        if not candidate.exists():
            return candidate
        i += 1


# --- Загрузка одного изображения ---
async def download_image(session, url, save_dir, slot, idx):
    """slot — список [url, status]; обновляем slot[1] по результату."""
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with session.get(url, timeout=timeout) as resp:
            resp.raise_for_status()
            data = await resp.read()
        if not data:
            raise ValueError("пустой ответ (нет данных)")
        out = unique_path(save_dir, filename_from_url(url))
        # запись файла в потоке, чтобы не блокировать event loop
        await asyncio.to_thread(_write_bytes, out, data)
        slot[1] = "Успех"
    except Exception:
        slot[1] = "Ошибка"


def _write_bytes(path, data):
    with open(path, "wb") as f:
        f.write(data)


# --- Таблица ---
def fmt_table(headers, rows, aligns):
    ncol = len(headers)
    width = []
    for i in range(ncol):
        w = len(headers[i])
        for r in rows:
            w = max(w, len(str(r[i])))
        width.append(w + 2)

    def sep():
        return "+" + "+".join("-" * w for w in width) + "+"

    def line(cells):
        out = []
        for i, c in enumerate(cells):
            s = str(c)
            if aligns[i] == "c":
                out.append(s.center(width[i]))
            else:
                out.append(" " + s.ljust(width[i] - 1))
        return "|" + "|".join(out) + "|"

    res = [sep(), line(headers), sep()]
    for r in rows:
        res.append(line(r))
    res.append(sep())
    return "\n".join(res)


def print_summary(results):
    rows = [[url, status] for url, status in results]
    print()
    print("Сводка об успешных и неуспешных загрузках")
    print()
    print(fmt_table(["Ссылка", "Статус"], rows, ["l", "c"]))
    ok = sum(1 for _, s in results if s == "Успех")
    fail = sum(1 for _, s in results if s == "Ошибка")
    print()
    print(f"Успешно: {ok}, Ошибок: {fail}, Всего: {len(results)}")


# --- Основная логика ---
async def main():
    save_dir = await asyncio.to_thread(prompt_save_dir)
    print(f"Сохранение в: {save_dir.resolve()}")

    results = []          # список [url, status] в порядке ввода
    tasks = []
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while True:
            url = await asyncio.to_thread(
                input, "Введите ссылку на изображение (пустая строка — завершить): "
            )
            url = url.strip()
            if not url:
                break
            slot = [url, None]
            results.append(slot)
            task = asyncio.create_task(
                download_image(session, url, save_dir, slot, len(results) - 1)
            )
            tasks.append(task)

        # После пустой строки: ждём завершения всех загрузок
        pending = [t for t in tasks if not t.done()]
        if pending:
            print(f"Ещё загружается изображений: {len(pending)}. Ожидание завершения...")
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    # финальная сводка
    final = [[url, (status or "Ошибка")] for url, status in results]
    print_summary(final)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрервано пользователем.")
        sys.exit(130)
