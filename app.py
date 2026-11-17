import streamlit as st
from google import genai
from google.genai import types
import time

st.set_page_config(page_title="Transcritor de Exames", page_icon="🩺", layout="centered")

st.title("🩺 Transcritor de Exames para Prontuário")
st.info("Aviso de privacidade: Nenhum arquivo fica salvo neste site. Para maior segurança, oculte o nome e CPF do paciente antes de enviar.")

SYSTEM_INSTRUCTION = """
Você é um assistente médico especializado em transcrição de exames laboratoriais para prontuário eletrônico.
Extraia TODOS os resultados de exames presentes no documento e forneça um resumo compacto e direto, organizado por data (se houver mais de uma) e categoria/painel.

REGRAS ESTRITAS:
1. NÃO inclua valores de referência.
2. NÃO adicione introduções, saudações, comentários clínicos ou conclusões.
3. Use formato compacto separado por barras na mesma linha por grupo de exames (ex: Hemograma (DD/MM/AAAA): Hb 13,5 | Ht 40% | Leuco 6.500 | Plaq 250.000).
4. Destaque apenas alterações relevantes com asterisco (*) se estiverem explicitamente sinalizadas no laudo, mantendo a concisão.
5. Mantenha as unidades de medida apenas quando essenciais para evitar ambiguidade.
"""

api_key = st.secrets.get("GEMINI_API_KEY") if "GEMINI_API_KEY" in st.secrets else None

if not api_key:
    api_key = st.sidebar.text_input("Insira sua Gemini API Key", type="password")

uploaded_file = st.file_uploader("Clique abaixo para escolher o PDF do exame", type=["pdf"])

if uploaded_file is not None:
    if not api_key:
        st.warning("⚠️ Chave da API não configurada.")
    else:
        if st.button("Transcrever Exame", type="primary"):
            with st.spinner("Lendo PDF e organizando resultados..."):
                client = genai.Client(api_key=api_key)
                pdf_bytes = uploaded_file.getvalue()
                
                modelos = ["gemini-3.8-flash", "gemini-3.8-flash-lite", "gemini-3.5-flash"]
                sucesso = False
                ultimo_erro = ""

                for modelo in modelos:
                    for tentativa in range(2):
                        try:
                            response = client.models.generate_content(
                                model=modelo,
                                contents=[
                                    types.Part.from_bytes(
                                        data=pdf_bytes,
                                        mime_type="application/pdf",
                                    ),
                                    "Transcreva os resultados deste exame seguindo rigorosamente as instruções do sistema."
                                ],
                                config=types.GenerateContentConfig(
                                    system_instruction=SYSTEM_INSTRUCTION,
                                    temperature=0.1,
                                )
                            )
                            st.subheader("Resultado Pronto para Copiar:")
                            st.code(response.text, language="text")
                            st.caption("Passe o mouse no canto superior direito da caixa cinza acima e clique no ícone de copiar.")
                            sucesso = True
                            break
                        except Exception as e:
                            ultimo_erro = str(e)
                            if "503" in ultimo_erro or "UNAVAILABLE" in ultimo_erro:
                                time.sleep(2)
                                continue
                            else:
                                break
                    if sucesso:
                        break

                if not sucesso:
                    st.error(f"Os servidores estão temporariamente sobrecarregados. Tente novamente em alguns segundos. Detalhe: {ultimo_erro}")
