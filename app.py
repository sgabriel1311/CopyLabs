import streamlit as st
from google import genai
from google.genai import types
from pypdf import PdfReader
import io

st.set_page_config(page_title="Transcritor de Exames", page_icon="🩺", layout="centered")

st.title("🩺 Transcritor de Exames para Prontuário")
st.info("Aviso de privacidade: Nenhum arquivo fica salvo neste site. Para maior segurança, oculte o nome e CPF do paciente antes de enviar.")

SYSTEM_INSTRUCTION = """
Você é um assistente médico especializado em transcrição de exames laboratoriais para evolução em prontuário eletrônico.
Extraia TODOS os resultados de exames presentes e organize-os estritamente em texto corrido por data.

REGRAS ESTRITAS DE FORMATAÇÃO:
1. NÃO use Markdown (proibido usar **, *, #, listas ou quebras de linha dentro da mesma data). O resultado deve ser texto puro pronto para colar em prontuário.
2. NÃO inclua valores de referência, introduções, saudações ou comentários clínicos.
3. Inicie cada data no formato exato: (DD/MM/AAAA): seguido de todos os exames daquela data na mesma linha contínua, separados por " / ".
4. NÃO agrupe por categorias (não escreva "Hemograma:", "Bioquímica:" ou "Coagulação:"). Liste os parâmetros diretamente em sequência. Exceção: para gasometria, identifique como GASO ARTERIAL: ou GASO VENOSA: antes dos seus parâmetros.
5. Utilize exatamente esta nomenclatura padrão:
   - Gasometria: GASO ARTERIAL: pH X / pCO2 X / pO2 X / BE X / HCO3 X / satO2 X% / FIO2 X (se informado)
   - Hemograma: Hemoglobina X / Hematocrito X% / Leucócitos X / Bastões X% / Meta X% / Mielo X% / Plaquetas X
   - Função Renal/Eletrólitos/Inflamatórios: Uréia X / Creatinina X / PCR X / Sódio X / Potássio X / Magnésio X / Cálcio Total X / Cálcio Iônico X / Fósforo X
   - Hepático/Enzimas: TGO X / TGP X / Bilirrubina total X / BD X / BI X / GGT X / FA X / Amilase X / Lipase X / CPK X / Troponina X / D-DÍMERO: X / Lactato (unidade) X
   - Coagulograma: TAP X% / RNI X / TTPa X / Relação X
   - Proteínas: Proteínas Totais X / Albumina X
6. Omita unidades de medida padrão para manter a concisão, mantendo apenas "%" quando aplicável e unidades específicas quando necessário para evitar ambiguidade (ex: Lactato (mg/dL) ou (mmol/L)).
7. Se houver exames de datas diferentes no mesmo PDF, coloque cada data em um parágrafo separado seguindo o mesmo padrão (DD/MM/AAAA):.

EXEMPLO DE SAÍDA ESPERADA:
(13/11/2026): GASO ARTERIAL: pH 7,360 / pCO2 40,0 / pO2 57,0 / BE -2,1 / HCO3 23,2 / satO2 89,0% / FIO2 4 L / Lactato (mg/dL) 9 / Troponina 12,8 / D-DÍMERO: > 7650 / Hemoglobina 8,1 / Hematocrito 25,6% / Leucócitos 71.380 / Bastões 0,0% / Meta 0,0% / Mielo 0,0% / Plaquetas 399.000 / Uréia 88 / Creatinina 2,20 / PCR 214,5 / Sódio 140 / Potássio 4,2 / Magnésio 1,5 / TGO 16 / TGP 10 / Bilirrubina total 0,2 / BD 0,2 / BI 0,0 / TAP 77,0% / RNI 1,16 / TTPa 23,6 / Relação 0,82 / Proteínas Totais 4,6 / Albumina 2,0
"""

def extrair_texto_rapido(pdf_bytes):
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        texto = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        return texto if len(texto) > 50 else None
    except Exception:
        return None

api_key = st.secrets.get("GEMINI_API_KEY") if "GEMINI_API_KEY" in st.secrets else None

if not api_key:
    api_key = st.sidebar.text_input("Insira sua Gemini API Key", type="password")

uploaded_file = st.file_uploader("Selecione ou arraste o PDF do exame", type=["pdf"])

if uploaded_file is not None:
    if not api_key:
        st.warning("⚠️ Chave da API não configurada.")
    else:
        file_id = f"{uploaded_file.name}_{uploaded_file.size}"
        
        if st.session_state.get("last_file_id") != file_id:
            client = genai.Client(api_key=api_key)
            pdf_bytes = uploaded_file.getvalue()
            
            # Tenta extrair texto puro localmente em milissegundos
            texto_extraido = extrair_texto_rapido(pdf_bytes)
            
            if texto_extraido:
                conteudo_envio = [f"Transcreva os resultados deste laudo seguindo rigorosamente o formato do exemplo:\n\n{texto_extraido}"]
            else:
                # Fallback visual caso o PDF seja escaneado/imagem
                conteudo_envio = [
                    types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                    "Transcreva os resultados seguindo rigorosamente o formato do exemplo."
                ]

            # Modelos ultra-rápidos em ordem de velocidade
            modelos = ["gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-3.8-pro"]
            sucesso = False
            texto_completo = ""

            st.subheader("Resultado Pronto para Copiar:")
            output_area = st.empty()

            for modelo in modelos:
                try:
                    response_stream = client.models.generate_content_stream(
                        model=modelo,
                        contents=conteudo_envio,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_INSTRUCTION,
                            temperature=0.0,
                            thinking_config=types.ThinkingConfig(thinking_budget=0),
                        )
                    )
                    
                    for chunk in response_stream:
                        if chunk.text:
                            texto_completo += chunk.text
                            output_area.code(texto_completo, language="text")
                    
                    st.session_state["last_file_id"] = file_id
                    st.session_state["last_result"] = texto_completo
                    sucesso = True
                    break

                except Exception as e:
                    erro_str = str(e)
                    if any(code in erro_str for code in ["503", "UNAVAILABLE", "429", "404"]):
                        continue
                    else:
                        output_area.error(f"Erro ao processar: {erro_str}")
                        break

            if not sucesso and not texto_completo:
                output_area.error("Servidores temporariamente ocupados. Tente enviar novamente em alguns segundos.")
        else:
            st.subheader("Resultado Pronto para Copiar:")
            st.code(st.session_state.get("last_result", ""), language="text")

        if st.session_state.get("last_result"):
            st.caption("Passe o mouse no canto superior direito da caixa cinza acima e clique no ícone de copiar.")
