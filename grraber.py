import asyncio
import os
import re
from playwright.async_api import async_playwright

# --- НАСТРОЙКИ ---
LOGIN = os.getenv('LOGIN', 'ВАШ_ЛОГИН')
PASSWORD = os.getenv('PASSWORD', 'ВАШ_ПАРОЛЬ')

# Список каналов: Название -> Ссылка на страницу
CHANNELS = {
    "Первый канал": "",
    "Россия 1": "",
    "НТВ": "",
    "ТНТ": ""
}

# Шаблон выходной ссылки
STREAM_BASE_URL = "htttps://server.smotrettv.com/{channel_id}.m3u8?token={token}"

async def get_playlist():
    async with async_playwright() as p:
        # Запуск браузера (headless=False если хотите видеть процесс)
        browser = await p.chromium.launch(headless=True)
        # Эмуляция реального пользователя
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            # 1. АВТОРИЗАЦИЯ
            print(f"[*] Вход в аккаунт {LOGIN}...")
            await page.goto("smotrettv.com", wait_until="networkidle")
            await page.fill('input[name="email"]', LOGIN)
            await page.fill('input[name="password"]', PASSWORD)
            await page.click('button[type="submit"]')
            
            # Ждем завершения редиректа после логина
            await page.wait_for_url("smotrettv.com", timeout=10000)
            print("[+] Авторизация успешна")

        except Exception as e:
            print(f"[!] Ошибка авторизации: {e}")
            await browser.close()
            return

        playlist_lines = ["#EXTM3U"]

        # 2. СБОР ТОКЕНОВ ДЛЯ КАЖДОГО КАНАЛА
        for name, channel_url in CHANNELS.items():
            print(f"[*] Получение токена для: {name}...")
            current_token = None

            # Функция-перехватчик сетевых запросов
            def intercept_requests(request):
                nonlocal current_token
                # Ищем URL, содержащий 'token=' в запросах к серверу вещания
                if "token=" in request.url:
                    match = re.search(r'token=([a-zA-Z0-9.\-_]+)', request.url)
                    if match:
                        current_token = match.group(1)

            page.on("request", intercept_requests)

            try:
                # Переходим на страницу канала
                await page.goto(channel_url, wait_until="networkidle")
                
                # Ждем появления токена (имитируем просмотр для срабатывания плеера)
                # В 2026 году плееру может требоваться до 5-10 секунд для инициализации
                for _ in range(10): 
                    if current_token: break
                    await asyncio.sleep(1)

                if current_token:
                    # Извлекаем ID из URL (цифра в начале или вся последняя часть)
                    channel_id = channel_url.split("/")[-1]
                    # Если ID содержит текст (напр. '1-pervyy-kanal'), берем только цифру если нужно, 
                    # но обычно сервер принимает полный слаг.
                    
                    final_url = STREAM_BASE_URL.format(channel_id=channel_id, token=current_token)
                    
                    # Формат для DRM-play / Kodi
                    playlist_lines.append(f'#EXTINF:-1, {name}')
                    playlist_lines.append(f'#KODIPROP:inputstream.adaptive.license_type=widevine')
                    playlist_lines.append(f'#EXTVLCOPT:http-user-agent=Mozilla/5.0')
                    playlist_lines.append(final_url)
                    print(f"    [OK] Токен получен")
                else:
                    print(f"    [FAIL] Токен не найден. Проверьте подписку на аккаунте.")

            except Exception as e:
                print(f"    [!] Ошибка на канале {name}: {e}")
            
            # Очищаем обработчик для следующего канала
            page.remove_listener("request", intercept_requests)

        # 3. СОХРАНЕНИЕ
        with open("smotrettv_playlist.m3u", "w", encoding="utf-8") as f:
            f.write("\n".join(playlist_lines))
        
        print("\n" + "="*30)
        print("[ЗАВЕРШЕНО] Файл 'smotrettv_playlist.m3u' создан.")
        print("="*30)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_playlist())
