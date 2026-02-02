from http.server import BaseHTTPRequestHandler
import json
import os

def call_openai(prompt, temperature=0):
    """OpenAI API 호출"""
    try:
        import urllib.request

        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            return None

        data = json.dumps({
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature
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
    prompt = f"다음 한국어 텍스트의 띄어쓰기만 교정해주세요. 내용은 절대 바꾸지 말고 띄어쓰기만 수정하세요:\n\n{text}"
    result = call_openai(prompt, temperature=0)
    return result if result else text

def summarize_text(text):
    """텍스트 요약 및 정리"""
    prompt = f"""다음은 대학 합격생의 생기부 분석 내용입니다. 이 내용을 깔끔하게 정리해주세요.

규칙:
1. 핵심 포인트를 3-5개의 bullet point로 정리
2. 각 포인트는 한 문장으로 간결하게
3. "→" 기호 뒤의 내용은 핵심 인사이트이므로 반드시 포함
4. 불필요한 반복 제거
5. HTML 형식으로 출력 (<ul><li>...</li></ul>)

원문:
{text}

정리된 내용:"""
    result = call_openai(prompt, temperature=0.3)
    return result if result else text

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            text = data.get('text', '')
            mode = data.get('mode', 'format')  # 'format' or 'summarize'

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
