"""Pages synthétiques locales pour les tests Streamlit, sans accès à TikTok."""
TAG = """<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0">
<button id="ready" style="position:absolute;left:20px;top:20px;width:220px;height:60px"
onclick="window.ready=true;update()">Autoriser la collecte de test</button>
<input type="range" id="slider" min="0" max="100" value="0" style="position:absolute;left:20px;top:120px;width:300px;height:30px;margin:0" oninput="update()">
<input id="word" style="position:absolute;left:20px;top:200px;width:300px;height:40px" oninput="update()">
<main id="posts" hidden style="position:absolute;top:280px">
<a href="https://www.tiktok.com/@fixture/video/1234567890">Publication de test</a></main>
<script>function update(){document.getElementById('posts').hidden = !(window.ready && Number(document.getElementById('slider').value)>70 && document.getElementById('word').value==='été');}</script>
</body></html>"""
CAPTION = 'Café & découvertes 🍋\nUne escapade en été #tourisme'

