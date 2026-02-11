from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, render_template_string
import requests
import os
import json
from datetime import datetime
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

app = Flask(__name__)
app.secret_key = "segredo_super_secreto_leanttro_admin" # Necessário para sessões e mensagens flash

# --- CONFIGURAÇÕES ---
raw_url = os.getenv("DIRECTUS_URL", "https://api2.leanttro.com")
DIRECTUS_URL = raw_url.rstrip('/')

DIRECTUS_TOKEN = os.getenv("DIRECTUS_TOKEN", "") 
LOJA_ID = os.getenv("LOJA_ID", "") 

# --- FUNÇÕES AUXILIARES ---
def get_headers():
    return {"Authorization": f"Bearer {DIRECTUS_TOKEN}"} if DIRECTUS_TOKEN else {}

def get_img_url(image_id_or_url):
    if not image_id_or_url: return ""
    if isinstance(image_id_or_url, dict): return f"{DIRECTUS_URL}/assets/{image_id_or_url.get('id')}"
    if image_id_or_url.startswith('http'): return image_id_or_url
    return f"{DIRECTUS_URL}/assets/{image_id_or_url}"

def upload_file(file_obj):
    """Envia arquivo para o Directus e retorna o ID"""
    if not file_obj or file_obj.filename == '': return None
    try:
        files = {'file': (file_obj.filename, file_obj.read(), file_obj.content_type)}
        resp = requests.post(f"{DIRECTUS_URL}/files", headers=get_headers(), files=files)
        if resp.status_code == 200:
            return resp.json()['data']['id']
    except Exception as e:
        print(f"Erro upload: {e}")
    return None

def get_loja_data():
    default_data = {"nome": "Tech Store", "cor_primaria": "#7c3aed", "whatsapp": ""}
    try:
        if LOJA_ID:
            url = f"{DIRECTUS_URL}/items/lojas/{LOJA_ID}?fields=*.*"
            resp = requests.get(url, headers=get_headers())
            if resp.status_code == 200:
                data = resp.json().get('data', {})
                logo_raw = data.get('logo')
                logo_final = logo_raw.get('id') if isinstance(logo_raw, dict) else logo_raw
                
                # Campos extras para o admin
                data['logo_url'] = get_img_url(logo_final)
                data['banner1_url'] = get_img_url(data.get('bannerprincipal1'))
                data['banner2_url'] = get_img_url(data.get('bannerprincipal2'))
                data['bannermenor1_url'] = get_img_url(data.get('bannermenor1'))
                data['bannermenor2_url'] = get_img_url(data.get('bannermenor2'))
                
                # Senha do Admin (Assumindo que o campo no Directus é 'senha_admin')
                data['senha_admin'] = data.get('senha_admin') 

                # Mapeamento do layout
                data['slug_url'] = 'tecnologia' 
                return data
    except Exception as e: print(f"Erro Loja: {e}")
    return default_data

def get_categorias():
    try:
        url = f"{DIRECTUS_URL}/items/categorias?filter[loja_id][_eq]={LOJA_ID}&filter[status][_eq]=published&sort=sort"
        resp = requests.get(url, headers=get_headers())
        if resp.status_code == 200: return resp.json().get('data', [])
    except: pass
    return []

# --- ROTAS PÚBLICAS (Leitura) ---

@app.route('/tecnologia/')
def index():
    loja = get_loja_data()
    categorias = get_categorias()
    cat_filter = request.args.get('categoria')
    filter_str = f"&filter[loja_id][_eq]={LOJA_ID}&filter[status][_eq]=published"
    if cat_filter: filter_str += f"&filter[categoria_id][_eq]={cat_filter}"

    produtos = []
    try:
        url_prod = f"{DIRECTUS_URL}/items/produtos?{filter_str}&fields=*.*"
        resp_prod = requests.get(url_prod, headers=get_headers())
        if resp_prod.status_code == 200:
            for p in resp_prod.json().get('data', []):
                img_url = get_img_url(p.get('imagem_destaque') or p.get('imagem1')) or "https://placehold.co/600x600/111827/FFF?text=Sem+Imagem"
                
                variantes_tratadas = []
                if p.get('variantes'):
                    v_list = p['variantes'] if isinstance(p['variantes'], list) else []
                    for v in v_list:
                        v_img = get_img_url(v.get('foto')) if v.get('foto') else img_url
                        variantes_tratadas.append({"nome": v.get('nome', 'Padrão'), "foto": v_img})

                produtos.append({
                    "id": str(p['id']), 
                    "nome": p['nome'],
                    "slug": p.get('slug'),
                    "preco": float(p['preco']) if p.get('preco') else None,
                    "imagem": img_url,
                    "origem": p.get('origem', 'Estoque'), 
                    "urgencia": p.get('status_urgencia', 'Normal'), 
                    "variantes": variantes_tratadas,
                    "categoria_id": p.get('categoria_id')
                })
    except Exception as e: print(f"Erro Index: {e}")

    posts = []
    try:
        url_posts = f"{DIRECTUS_URL}/items/posts?filter[loja_id][_eq]={LOJA_ID}&filter[status][_eq]=published&limit=5&sort=-date_created"
        resp_posts = requests.get(url_posts, headers=get_headers())
        if resp_posts.status_code == 200:
            for p in resp_posts.json().get('data', []):
                data_fmt = ""
                if p.get('date_created'):
                    try: dt = datetime.fromisoformat(p['date_created'].replace('Z', '+00:00')); data_fmt = dt.strftime('%d/%m/%Y')
                    except: pass
                posts.append({"titulo": p.get('titulo'), "resumo": p.get('resumo'), "capa": get_img_url(p.get('capa')), "slug": p.get('slug'), "data": data_fmt})
    except: pass

    return render_template('index.html', loja=loja, categorias=categorias, produtos=produtos, posts=posts, directus_url=DIRECTUS_URL)

@app.route('/tecnologia/produto/<slug>')
def produto_detalhe(slug):
    loja = get_loja_data()
    try:
        url = f"{DIRECTUS_URL}/items/produtos?filter[slug][_eq]={slug}&filter[loja_id][_eq]={LOJA_ID}&fields=*.*"
        resp = requests.get(url, headers=get_headers())
        if resp.status_code == 200 and len(resp.json()['data']) > 0:
            p = resp.json()['data'][0]
            img_url = get_img_url(p.get('imagem_destaque') or p.get('imagem1')) or "https://placehold.co/600x600/111827/FFF?text=Sem+Imagem"
            
            cat_nome = "Software"
            if isinstance(p.get('categoria_id'), dict):
                cat_nome = p.get('categoria_id', {}).get('nome')
            
            produto_data = {
                "id": str(p['id']),
                "nome": p['nome'],
                "slug": p.get('slug'),
                "descricao": p.get('descricao', 'Sem descrição detalhada.'),
                "preco": float(p['preco']) if p.get('preco') else None,
                "imagem": img_url,
                "urgencia": p.get('status_urgencia', 'Normal'),
                "categoria_nome": cat_nome
            }
            return render_template('produto.html', loja=loja, produto=produto_data, directus_url=DIRECTUS_URL)
        return "Produto não encontrado", 404
    except Exception as e:
        print(f"Erro Produto: {e}")
        return "Erro ao carregar produto", 500

@app.route('/tecnologia/case/<slug>')
def case_detalhe(slug):
    loja = get_loja_data()
    try:
        url = f"{DIRECTUS_URL}/items/posts?filter[slug][_eq]={slug}&filter[loja_id][_eq]={LOJA_ID}&fields=*.*"
        resp = requests.get(url, headers=get_headers())
        if resp.status_code == 200 and len(resp.json()['data']) > 0:
            p = resp.json()['data'][0]
            data_fmt = ""
            if p.get('date_created'):
                try: dt = datetime.fromisoformat(p['date_created'].replace('Z', '+00:00')); data_fmt = dt.strftime('%d/%m/%Y')
                except: pass
            post_data = {
                "titulo": p.get('titulo'), "resumo": p.get('resumo'), "conteudo": p.get('conteudo'),
                "capa": get_img_url(p.get('capa')), "data": data_fmt, "autor": "Equipe " + loja['nome']
            }
            return render_template('cases.html', loja=loja, case=post_data, directus_url=DIRECTUS_URL)
        return "Case não encontrado", 404
    except Exception as e: return "Erro ao carregar case", 500

# --- ROTAS ADMIN (Autenticação e Escrita) ---

# Rota de Login (Substitui o acesso direto)
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        senha_digitada = request.form.get('senha')
        loja = get_loja_data()
        
        # Verifica a senha cadastrada no Directus
        if loja.get('senha_admin') and senha_digitada == loja.get('senha_admin'):
            session['admin_logged_in'] = True
            return redirect('/admin/painel')
        else:
            flash("Senha incorreta!", "error")
    
    # Template simples de login embutido
    login_html = """
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Acesso Restrito</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-900 flex items-center justify-center h-screen">
        <div class="bg-white p-8 rounded-xl shadow-2xl w-full max-w-sm">
            <h2 class="text-2xl font-bold text-center mb-6 text-gray-800">Acesso Administrativo</h2>
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="bg-red-100 text-red-700 p-3 rounded mb-4 text-sm font-bold text-center">{{ message }}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            <form method="POST">
                <div class="mb-4">
                    <label class="block text-gray-700 text-sm font-bold mb-2">Senha de Acesso</label>
                    <input type="password" name="senha" class="shadow appearance-none border rounded w-full py-3 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline" placeholder="********" required autofocus>
                </div>
                <button type="submit" class="w-full bg-purple-600 hover:bg-purple-700 text-white font-bold py-3 px-4 rounded focus:outline-none focus:shadow-outline transition-colors">Entrar</button>
            </form>
            <p class="text-center mt-6"><a href="/tecnologia/" class="text-gray-500 text-xs hover:text-gray-700">← Voltar para a Loja</a></p>
        </div>
    </body>
    </html>
    """
    return render_template_string(login_html)

@app.route('/admin/painel')
def admin_painel():
    # Proteção de Rota
    if not session.get('admin_logged_in'):
        return redirect('/admin')

    loja = get_loja_data()
    categorias = get_categorias()
    
    produtos = []
    try:
        resp = requests.get(f"{DIRECTUS_URL}/items/produtos?filter[loja_id][_eq]={LOJA_ID}&fields=id,nome,preco,imagem_destaque,estoque,categoria_id.nome,status_urgencia,origem", headers=get_headers())
        if resp.status_code == 200:
            for p in resp.json().get('data', []):
                p['imagem'] = get_img_url(p.get('imagem_destaque'))
                p['categoria_nome'] = p.get('categoria_id', {}).get('nome') if isinstance(p.get('categoria_id'), dict) else "Sem Categoria"
                produtos.append(p)
    except: pass

    posts = []
    try:
        resp = requests.get(f"{DIRECTUS_URL}/items/posts?filter[loja_id][_eq]={LOJA_ID}&fields=id,slug,titulo,date_created,capa,resumo", headers=get_headers())
        if resp.status_code == 200:
            for p in resp.json().get('data', []):
                p['capa'] = get_img_url(p.get('capa'))
                posts.append(p)
    except: pass

    return render_template('painel.html', loja=loja, categorias=categorias, produtos=produtos, posts=posts, directus_url=DIRECTUS_URL)

@app.route('/admin/painel/salvar', methods=['POST'])
def admin_salvar_geral():
    if not session.get('admin_logged_in'): return redirect('/admin')
    
    data = {
        "nome": request.form.get('nome'),
        "whatsapp_comercial": request.form.get('whatsapp'),
        "cor_primaria": request.form.get('cor_primaria'),
        "linkbannerprincipal1": request.form.get('link1'),
        "linkbannerprincipal2": request.form.get('link2'),
        "ocultar_banner": True if request.form.get('ocultar_banner') else False,
        "titulo_produtos": request.form.get('titulo_produtos'),
        "titulo_blog": request.form.get('titulo_blog'),
        "layout_order": request.form.get('layout_order')
    }

    if 'logo' in request.files and request.files['logo'].filename: data['logo'] = upload_file(request.files['logo'])
    if 'bannerprincipal1' in request.files and request.files['bannerprincipal1'].filename: data['bannerprincipal1'] = upload_file(request.files['bannerprincipal1'])
    if 'bannerprincipal2' in request.files and request.files['bannerprincipal2'].filename: data['bannerprincipal2'] = upload_file(request.files['bannerprincipal2'])

    requests.patch(f"{DIRECTUS_URL}/items/lojas/{LOJA_ID}", headers=get_headers(), json=data)
    flash("Configurações salvas com sucesso!", "success")
    return redirect('/admin/painel')

@app.route('/admin/categoria/salvar', methods=['POST'])
def admin_salvar_categoria():
    if not session.get('admin_logged_in'): return redirect('/admin')
    
    cid = request.form.get('id')
    payload = {"nome": request.form.get('nome'), "loja_id": LOJA_ID, "status": "published"}
    
    if cid:
        requests.patch(f"{DIRECTUS_URL}/items/categorias/{cid}", headers=get_headers(), json=payload)
        flash("Categoria atualizada!", "success")
    else:
        requests.post(f"{DIRECTUS_URL}/items/categorias", headers=get_headers(), json=payload)
        flash("Categoria criada!", "success")
    return redirect('/admin/painel#categorias')

@app.route('/admin/produto/salvar', methods=['POST'])
def admin_salvar_produto():
    if not session.get('admin_logged_in'): return redirect('/admin')

    pid = request.form.get('id')
    slug = request.form.get('nome').lower().replace(' ', '-').replace('/', '').replace('?', '')
    
    payload = {
        "status": "published",
        "loja_id": LOJA_ID,
        "nome": request.form.get('nome'),
        "slug": slug,
        "descricao": request.form.get('descricao'),
        "preco": request.form.get('preco') if request.form.get('preco') else None,
        "categoria_id": request.form.get('categoria_id') if request.form.get('categoria_id') else None,
        "status_urgencia": request.form.get('status_urgencia'),
        "origem": request.form.get('origem')
    }

    if 'imagem' in request.files and request.files['imagem'].filename: payload['imagem_destaque'] = upload_file(request.files['imagem'])
    if 'imagem1' in request.files and request.files['imagem1'].filename: payload['imagem1'] = upload_file(request.files['imagem1'])
    if 'imagem2' in request.files and request.files['imagem2'].filename: payload['imagem2'] = upload_file(request.files['imagem2'])

    if pid:
        requests.patch(f"{DIRECTUS_URL}/items/produtos/{pid}", headers=get_headers(), json=payload)
        flash("Produto atualizado!", "success")
    else:
        requests.post(f"{DIRECTUS_URL}/items/produtos", headers=get_headers(), json=payload)
        flash("Produto criado!", "success")
    return redirect('/admin/painel#produtos')

@app.route('/admin/post/salvar', methods=['POST'])
def admin_salvar_post():
    if not session.get('admin_logged_in'): return redirect('/admin')

    pid = request.form.get('id')
    slug = request.form.get('titulo').lower().replace(' ', '-').replace('?', '')
    
    payload = {
        "status": "published",
        "loja_id": LOJA_ID,
        "titulo": request.form.get('titulo'),
        "slug": slug,
        "resumo": request.form.get('resumo'),
        "conteudo": request.form.get('conteudo')
    }

    if 'capa' in request.files and request.files['capa'].filename: payload['capa'] = upload_file(request.files['capa'])

    if pid and len(pid) > 5:
        requests.patch(f"{DIRECTUS_URL}/items/posts/{pid}", headers=get_headers(), json=payload)
    else:
        requests.post(f"{DIRECTUS_URL}/items/posts", headers=get_headers(), json=payload)
    
    flash("Post salvo!", "success")
    return redirect('/admin/painel#blog')

@app.route('/admin/<tipo>/excluir/<id>')
def admin_excluir(tipo, id):
    if not session.get('admin_logged_in'): return redirect('/admin')

    collection_map = {"categoria": "categorias", "produto": "produtos", "post": "posts"}
    if tipo in collection_map:
        requests.delete(f"{DIRECTUS_URL}/items/{collection_map[tipo]}/{id}", headers=get_headers())
        flash(f"{tipo.capitalize()} excluído.", "success")
    return redirect(f'/admin/painel#{collection_map[tipo]}')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/tecnologia/')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)