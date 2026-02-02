from http.server import BaseHTTPRequestHandler
import json
import os

def call_openai(prompt, temperature=0, max_tokens=500):
    """OpenAI API 호출"""
    try:
        import urllib.request

        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            print("No OPENAI_API_KEY found")
            return None

        data = json.dumps({
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens
        }).encode('utf-8')

        req = urllib.request.Request(
            'https://api.openai.com/v1/chat/completions',
            data=data,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result['choices'][0]['message']['content']
    except Exception as e:
        print(f"OpenAI error: {e}")
        return None

def format_text(text):
    """띄어쓰기 교정"""
    if not text or len(text.strip()) < 10:
        return text
    prompt = f"띄어쓰기만 교정하세요. 내용 변경 금지:\n{text}"
    result = call_openai(prompt, temperature=0, max_tokens=len(text) + 200)
    return result if result else text

def summarize_text(text):
    """텍스트 요약"""
    if not text or len(text.strip()) < 20:
        return text
    prompt = f"핵심만 2-3줄로 요약하세요. 각 줄 앞에 • 붙이세요:\n{text}"
    result = call_openai(prompt, temperature=0.2, max_tokens=300)
    return result if result else text

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            # 배치 모드
            if 'items' in data:
                items = data['items']
                results = {}

                for item in items:
                    key = item.get('key', '')
                    text = item.get('text', '')
                    mode = item.get('mode', 'format')

                    if mode == 'summarize':
                        results[key] = summarize_text(text)
                    else:
                        results[key] = format_text(text)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': True,
                    'results': results
                }).encode('utf-8'))
            else:
                # 단일 처리
                text = data.get('text', '')
                mode = data.get('mode', 'format')

                if mode == 'summarize':
                    result = summarize_text(text)
                else:
                    result = format_text(text)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': True,
                    'result': result
                }).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': False,
                'error': str(e)
            }).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
