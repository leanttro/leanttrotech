from flask import Flask, render_template, request, jsonify, redirect
import requests
import os
import json
from datetime import datetime
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
# Remove barra final para evitar duplicação na montagem de URLs
raw_url = os.getenv("DIRECTUS_URL", "https://api2.leanttro.com")
DIRECTUS_URL = raw_url.rstrip('/')

DIRECTUS_TOKEN = os.getenv("DIRECTUS_TOKEN", "") 
LOJA_ID = os.getenv("LOJA_ID", "") # IMPORTANTE: Esse ID deve bater com o banco

# --- FUNÇÕES AUXILIARES ---
def get_img_url(image_id_or_url):
    """Trata imagens vindas do Directus (ID) ou URLs externas"""
    if not image_id_or_url:
        return "" # Retorna vazio, o HTML deve lidar com placeholder
    
    if isinstance(image_id_or_url, dict):
        return f"{DIRECTUS_URL}/assets/{image_id_or_url.get('id')}"
    
    if image_id_or_url.startswith('http'):
        return image_id_or_url
    
    return f"{DIRECTUS_URL}/assets/{image_id_or_url}"

def get_headers():
    return {"Authorization": f"Bearer {DIRECTUS_TOKEN}"} if DIRECTUS_TOKEN else {}

def get_loja_data():
    """Busca dados da loja e mapeia para o formato do Template"""
    default_data = {"nome": "Tech Store", "cor_primaria": "#7c3aed", "whatsapp": ""}
    
    try:
        if LOJA_ID:
            # Busca campos específicos baseados no seu print de 'Lojas'
            url = f"{DIRECTUS_URL}/items/lojas/{LOJA_ID}?fields=*.*"
            print(f"🔍 Buscando Loja: {url}") # Debug
            resp = requests.get(url, headers=get_headers())
            
            if resp.status_code == 200:
                data = resp.json().get('data', {})
                
                logo_raw = data.get('logo')
                logo_final = logo_raw.get('id') if isinstance(logo_raw, dict) else logo_raw
                
                return {
                    "nome": data.get('nome', 'Tech Store'),
                    "logo": logo_final,
                    "cor_primaria": data.get('cor_primaria', '#7c3aed'),
                    "whatsapp": data.get('whatsapp_comercial', ''),
                    # Mapeamento exato com seus prints
                    "banner1": get_img_url(data.get('bannerprincipal1')),
                    "link1": data.get('linkbannerprincipal1', '#'),
                    "banner2": get_img_url(data.get('bannerprincipal2')),
                    "link2": data.get('linkbannerprincipal2', '#')
                }
            else:
                print(f"❌ Erro ao buscar loja: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"❌ Exceção Loja: {e}")
    return default_data

def get_categorias():
    try:
        url = f"{DIRECTUS_URL}/items/categorias?filter[loja_id][_eq]={LOJA_ID}&filter[status][_eq]=published&sort=sort"
        resp = requests.get(url, headers=get_headers())
        if resp.status_code == 200:
            return resp.json().get('data', [])
    except: pass
    return []

# --- ROTAS PRINCIPAIS (/tecnologia) ---

@app.route('/tecnologia/')
def index():
    loja = get_loja_data()
    categorias = get_categorias()
    
    # Filtro de Categoria
    cat_filter = request.args.get('categoria')
    filter_str = f"&filter[loja_id][_eq]={LOJA_ID}&filter[status][_eq]=published"
    
    # Se filtrar, adiciona a query.
    if cat_filter:
        filter_str += f"&filter[categoria_id][_eq]={cat_filter}"

    produtos = []
    
    try:
        # Busca produtos com campos relacionais
        url_prod = f"{DIRECTUS_URL}/items/produtos?{filter_str}&fields=*.*"
        print(f"📦 Buscando Produtos: {url_prod}") # Debug no console
        
        resp_prod = requests.get(url_prod, headers=get_headers())
        
        if resp_prod.status_code == 200:
            produtos_raw = resp_prod.json().get('data', [])
            print(f"✅ Produtos encontrados: {len(produtos_raw)}")
            
            for p in produtos_raw:
                # Tratamento de Imagem (imagem_destaque ou imagem1 do seu print)
                img_url = get_img_url(p.get('imagem_destaque') or p.get('imagem1'))
                
                # Se não tiver imagem (script inseriu sem foto), usa placeholder
                if not img_url:
                    img_url = "https://placehold.co/600x600/111827/FFF?text=Sem+Imagem"

                # Tratamento de Variantes (JSON repeater)
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
                    # Flags baseadas no seu print
                    "origem": p.get('origem', 'Estoque'), 
                    "urgencia": p.get('status_urgencia', 'Normal'), 
                    "variantes": variantes_tratadas,
                    "categoria_id": p.get('categoria_id')
                })
        else:
            print(f"❌ Erro API Produtos: {resp_prod.text}")
                
    except Exception as e:
        print(f"❌ Erro Geral Produtos: {e}")

    # Busca Posts (Cases)
    posts = []
    try:
        url_posts = f"{DIRECTUS_URL}/items/posts?filter[loja_id][_eq]={LOJA_ID}&filter[status][_eq]=published&limit=5&sort=-date_created"
        resp_posts = requests.get(url_posts, headers=get_headers())
        if resp_posts.status_code == 200:
            raw_posts = resp_posts.json().get('data', [])
            for p in raw_posts:
                data_fmt = ""
                if p.get('date_created'):
                    try: dt = datetime.fromisoformat(p['date_created'].replace('Z', '+00:00')); data_fmt = dt.strftime('%d/%m/%Y')
                    except: pass
                
                posts.append({
                    "titulo": p.get('titulo'),
                    "resumo": p.get('resumo'),
                    "capa": get_img_url(p.get('capa')),
                    "slug": p.get('slug'),
                    "data": data_fmt
                })
    except: pass

    # Renderiza index.html
    return render_template('index.html', loja=loja, categorias=categorias, produtos=produtos, posts=posts, directus_url=DIRECTUS_URL)

@app.route('/tecnologia/produto/<slug>')
def produto_detalhe(slug):
    # Redireciona para a home com ancora, já que é one-page ou modal
    return redirect(f"/tecnologia/#produto-{slug}") 

@app.route('/tecnologia/case/<slug>')
def case_detalhe(slug):
    loja = get_loja_data()
    post_data = None
    
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
                "titulo": p.get('titulo'),
                "resumo": p.get('resumo'),
                "conteudo": p.get('conteudo'),
                "capa": get_img_url(p.get('capa')),
                "data": data_fmt,
                "autor": "Equipe " + loja['nome']
            }
            return render_template('cases.html', loja=loja, case=post_data, directus_url=DIRECTUS_URL)
        else:
            return "Case não encontrado", 404
    except Exception as e:
        print(e)
        return "Erro ao carregar case", 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)