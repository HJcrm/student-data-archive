from http.server import BaseHTTPRequestHandler
import json
import os

def call_openai(prompt, temperature=0, max_tokens=1000):
    """OpenAI API 호출"""
    try:
        import urllib.request

        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
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

        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result['choices'][0]['message']['content']
    except Exception as e:
        print(f"OpenAI error: {e}")
        return None

def process_batch(items):
    """여러 텍스트를 한 번에 처리 (토큰 최소화)"""
    if not items:
        return {}

    # 프롬프트 구성
    prompt_parts = ["다음 텍스트들을 처리해주세요. 각 항목별로 지시사항을 따르세요.\n"]

    for i, item in enumerate(items):
        text = item.get('text', '')
        mode = item.get('mode', 'format')
        key = item.get('key', str(i))

        if mode == 'format':
            prompt_parts.append(f"[{key}] 띄어쓰기만 교정:\n{text}\n")
        elif mode == 'summarize':
            prompt_parts.append(f"[{key}] 핵심만 2-3줄로 요약 (• 기호 사용):\n{text}\n")

    prompt_parts.append("\n각 항목을 [키] 형식으로 구분하여 결과만 출력하세요.")

    full_prompt = "\n".join(prompt_parts)
    result = call_openai(full_prompt, temperature=0, max_tokens=2000)

    if not result:
        return {item.get('key', str(i)): item.get('text', '') for i, item in enumerate(items)}

    # 결과 파싱
    parsed = {}
    current_key = None
    current_content = []

    for line in result.split('\n'):
        # [키] 패턴 찾기
        if line.strip().startswith('[') and ']' in line:
            if current_key:
                parsed[current_key] = '\n'.join(current_content).strip()
            bracket_end = line.index(']')
            current_key = line[1:bracket_end]
            remaining = line[bracket_end+1:].strip()
            current_content = [remaining] if remaining else []
        elif current_key:
            current_content.append(line)

    if current_key:
        parsed[current_key] = '\n'.join(current_content).strip()

    return parsed

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            # 배치 모드 지원
            if 'items' in data:
                results = process_batch(data['items'])
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': True,
                    'results': results
                }).encode('utf-8'))
            else:
                # 단일 처리 (하위 호환)
                text = data.get('text', '')
                mode = data.get('mode', 'format')

                items = [{'key': '0', 'text': text, 'mode': mode}]
                results = process_batch(items)
                result = results.get('0', text)

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
