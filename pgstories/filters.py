"""Catálogo de filtros de imagem.

Todas as funções de filtro recebem uma imagem ``uint8`` que pode ter 1 canal
(H x W) ou 3 canais BGR (H x W x 3) e um dicionário com os parâmetros já
validados. Elas podem devolver 1 ou 3 canais: quem ajusta o resultado para o
modo de canal escolhido pelo usuário é o ``pipeline`` (ver ``pipeline.py``).

Referência principal: GONZALEZ, R. C.; WOODS, R. E. *Digital Image Processing*.
"""

from __future__ import annotations

from functools import lru_cache

import cv2
import numpy as np

from .params import EffectSpec, Param

# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------


def to_gray(img: np.ndarray) -> np.ndarray:
    return img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def to_bgr(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR) if img.ndim == 2 else img


def _odd(v: float) -> int:
    v = max(1, int(round(v)))
    return v if v % 2 else v + 1


def _clip_u8(arr: np.ndarray) -> np.ndarray:
    return np.clip(arr, 0, 255).astype(np.uint8)


def _lut(img: np.ndarray, table: np.ndarray) -> np.ndarray:
    return cv2.LUT(img, _clip_u8(table))


# ---------------------------------------------------------------------------
# Suavização (passa-baixa)
# ---------------------------------------------------------------------------


def box_blur(img, p):
    k = _odd(p["k"])
    return cv2.blur(img, (k, k))


def gaussian_blur(img, p):
    k = _odd(p["k"])
    return cv2.GaussianBlur(img, (k, k), p["sigma"])


def median_blur(img, p):
    return cv2.medianBlur(img, _odd(p["k"]))


def bilateral(img, p):
    return cv2.bilateralFilter(img, int(p["d"]), p["sigma_cor"], p["sigma_espaco"])


# ---------------------------------------------------------------------------
# Realce (passa-alta)
# ---------------------------------------------------------------------------


def sharpen(img, p):
    a = p["forca"]
    kernel = np.array([[0, -a, 0],
                       [-a, 1 + 4 * a, -a],
                       [0, -a, 0]], np.float32)
    return cv2.filter2D(img, -1, kernel)


def unsharp_mask(img, p):
    amount = p["quantidade"]
    blurred = cv2.GaussianBlur(img, (0, 0), p["sigma"])
    return cv2.addWeighted(img, 1 + amount, blurred, -amount, 0)


def laplacian(img, p):
    f = img.astype(np.float32)
    lap = cv2.Laplacian(f, cv2.CV_32F, ksize=int(p["ksize"]))
    if p["modo"] == "bordas":
        return cv2.convertScaleAbs(lap, alpha=p["ganho"])
    # Realce: g(x, y) = f(x, y) - c * laplaciano(f)  (centro do kernel negativo)
    return _clip_u8(f - p["ganho"] * lap)


# ---------------------------------------------------------------------------
# Bordas
# ---------------------------------------------------------------------------


def sobel(img, p):
    f = img.astype(np.float32)
    k = int(p["ksize"])
    gx = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=k)
    gy = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=k)
    if p["direcao"] == "x":
        mag = np.abs(gx)
    elif p["direcao"] == "y":
        mag = np.abs(gy)
    else:
        mag = np.sqrt(gx * gx + gy * gy)
    return cv2.convertScaleAbs(mag, alpha=p["ganho"])


def canny(img, p):
    gray = cv2.GaussianBlur(to_gray(img), (5, 5), 0)
    edges = cv2.Canny(gray, p["limiar_baixo"], p["limiar_alto"], L2gradient=True)
    if p["espessura"] > 1:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(p["espessura"]),) * 2)
        edges = cv2.dilate(edges, k)
    return cv2.bitwise_not(edges) if p["fundo_branco"] else edges


def emboss(img, p):
    s = p["forca"]
    if p["estilo"] == "cinza":
        kernel = s * np.array([[-1, -1, 0], [-1, 0, 1], [0, 1, 1]], np.float32)
        out = cv2.filter2D(to_gray(img).astype(np.float32), cv2.CV_32F, kernel) + 128
        return _clip_u8(out)
    kernel = s * np.array([[-2, -1, 0], [-1, 0, 1], [0, 1, 2]], np.float32)
    kernel[1, 1] = 1.0
    return cv2.filter2D(img, -1, kernel)


# ---------------------------------------------------------------------------
# Cor e tom (operações pontuais)
# ---------------------------------------------------------------------------


def grayscale(img, p):
    return to_gray(img)


def negative(img, p):
    return cv2.bitwise_not(img)


def brightness_contrast(img, p):
    # g(x) = alfa * f(x) + beta, com saturação em [0, 255]
    return cv2.addWeighted(img, p["contraste"], img, 0, p["brilho"])


def gamma_correction(img, p):
    table = ((np.arange(256) / 255.0) ** p["gama"]) * 255.0 + 0.5
    return _lut(img, table)


def equalize(img, p):
    if p["metodo"] == "clahe":
        clahe = cv2.createCLAHE(clipLimit=p["limite"], tileGridSize=(int(p["blocos"]),) * 2)
        eq = clahe.apply
    else:
        eq = cv2.equalizeHist
    if img.ndim == 2:
        return eq(img)
    # Em imagens coloridas equalizamos só a luminância (Y) para não distorcer as cores.
    y, cr, cb = cv2.split(cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb))
    return cv2.cvtColor(cv2.merge([eq(y), cr, cb]), cv2.COLOR_YCrCb2BGR)


def saturation(img, p):
    if img.ndim == 2:
        return img
    h, s, v = cv2.split(cv2.cvtColor(img, cv2.COLOR_BGR2HSV))
    s = _clip_u8(s.astype(np.float32) * p["fator"])
    return cv2.cvtColor(cv2.merge([h, s, v]), cv2.COLOR_HSV2BGR)


def temperature(img, p):
    if img.ndim == 2:
        return img
    t = p["temperatura"]
    x = np.arange(256, dtype=np.float32)
    warm_r = x + t * 0.6 * (1 - x / 400)
    cool_b = x - t * 0.6 * (1 - x / 400)
    b, g, r = cv2.split(img)
    return cv2.merge([_lut(b, cool_b), _lut(g, x + t * 0.1), _lut(r, warm_r)])


def sepia(img, p):
    bgr = to_bgr(img)
    # Matriz clássica de sépia, escrita para a ordem de canais BGR do OpenCV.
    m = np.array([[0.131, 0.534, 0.272],
                  [0.168, 0.686, 0.349],
                  [0.189, 0.769, 0.393]], np.float32)
    tone = cv2.transform(bgr, m)
    return cv2.addWeighted(tone, p["intensidade"], bgr, 1 - p["intensidade"], 0)


COLORMAPS = (
    ("INFERNO", "Inferno"), ("JET", "Jet (arco-íris)"), ("VIRIDIS", "Viridis"),
    ("MAGMA", "Magma"), ("TURBO", "Turbo"), ("HOT", "Calor (hot)"),
    ("OCEAN", "Oceano"), ("PINK", "Rosa"), ("TWILIGHT", "Crepúsculo"), ("COOL", "Frio"),
)


def pseudocolor(img, p):
    cmap = getattr(cv2, f"COLORMAP_{p['mapa']}", cv2.COLORMAP_JET)
    return cv2.applyColorMap(to_gray(img), cmap)


def threshold(img, p):
    gray = to_gray(img)
    method = p["metodo"]
    if method == "otsu":
        _, out = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    elif method == "adaptativo":
        out = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY, _odd(p["bloco"]), p["c"])
    elif method == "invertido":
        _, out = cv2.threshold(gray, p["limiar"], 255, cv2.THRESH_BINARY_INV)
    else:
        _, out = cv2.threshold(gray, p["limiar"], 255, cv2.THRESH_BINARY)
    return out


# ---------------------------------------------------------------------------
# Morfologia
# ---------------------------------------------------------------------------

MORPH_OPS = {
    "abertura": cv2.MORPH_OPEN, "fechamento": cv2.MORPH_CLOSE,
    "gradiente": cv2.MORPH_GRADIENT, "tophat": cv2.MORPH_TOPHAT, "blackhat": cv2.MORPH_BLACKHAT,
}


def morphology(img, p):
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (_odd(p["k"]),) * 2)
    it = int(p["iteracoes"])
    op = p["operacao"]
    if op == "erosao":
        return cv2.erode(img, k, iterations=it)
    if op == "dilatacao":
        return cv2.dilate(img, k, iterations=it)
    return cv2.morphologyEx(img, MORPH_OPS[op], k, iterations=it)


# ---------------------------------------------------------------------------
# Estilo
# ---------------------------------------------------------------------------


def posterize(img, p):
    n = int(p["niveis"])
    step = 256.0 / n
    table = np.floor(np.arange(256) / step) * step + step / 2
    return _lut(img, table)


def pixelate(img, p):
    b = int(p["bloco"])
    h, w = img.shape[:2]
    small = cv2.resize(img, (max(1, w // b), max(1, h // b)), interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)


@lru_cache(maxsize=16)
def _vignette_mask(h: int, w: int, strength: float, radius: float) -> np.ndarray:
    y, x = np.ogrid[:h, :w]
    nx = (x - (w - 1) / 2) / ((w - 1) / 2 or 1)
    ny = (y - (h - 1) / 2) / ((h - 1) / 2 or 1)
    d = np.sqrt(nx * nx + ny * ny) / np.sqrt(2)  # 0 no centro, 1 nos cantos
    t = np.clip((d - radius) / max(1e-6, 1 - radius), 0, 1)
    t = t * t * (3 - 2 * t)  # smoothstep: transição suave
    return (1 - strength * t).astype(np.float32)


def vignette(img, p):
    h, w = img.shape[:2]
    mask = _vignette_mask(h, w, round(p["forca"], 3), round(p["raio"], 3))
    if img.ndim == 3:
        mask = mask[:, :, None]
    return _clip_u8(img.astype(np.float32) * mask)


def cartoon(img, p):
    # O bilateral é aplicado em meia resolução (bem mais rápido para o vídeo).
    h, w = img.shape[:2]
    color = cv2.resize(img, (max(1, w // 2), max(1, h // 2)), interpolation=cv2.INTER_AREA)
    for _ in range(int(p["suavizacao"])):
        color = cv2.bilateralFilter(color, 7, 50, 50)
    color = cv2.resize(color, (w, h), interpolation=cv2.INTER_LINEAR)
    color = posterize(color, {"niveis": p["cores"]})
    gray = cv2.medianBlur(to_gray(img), 7)
    edges = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY,
                                  _odd(p["bordas"]), 2)
    if color.ndim == 3:
        edges = to_bgr(edges)
    return cv2.bitwise_and(color, edges)


# ---------------------------------------------------------------------------
# Ruído (útil para testar os filtros de suavização)
# ---------------------------------------------------------------------------


def add_noise(img, p):
    rng = np.random.default_rng(int(p["semente"]))
    amount = p["quantidade"]
    if p["tipo"] == "gaussiano":
        noise = rng.normal(0.0, amount, img.shape).astype(np.float32)
        return _clip_u8(img.astype(np.float32) + noise)
    prob = amount / 400.0  # quantidade 100 -> 25% dos pixels
    r = rng.random(img.shape[:2])
    out = img.copy()
    out[r < prob / 2] = 0
    out[r > 1 - prob / 2] = 255
    return out


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------

K_HELP = "tamanho da janela (vizinhança) usada no cálculo; quanto maior, mais forte o efeito."

FILTERS: tuple[EffectSpec, ...] = (
    # --- Suavização ---------------------------------------------------------
    EffectSpec(
        "box", "Desfoque de caixa (Box / média)", "Suavização",
        "Substitui cada pixel pela média simples dos vizinhos dentro de uma janela k×k. "
        "É o filtro passa-baixa mais simples: reduz ruído e detalhes finos, mas também borra as bordas.",
        box_blur,
        (Param("k", "Tamanho do kernel", "int", 7, 3, 51, 2, odd=True, short="k", help=K_HELP),),
    ),
    EffectSpec(
        "gaussian", "Desfoque gaussiano (Gaussian Blur)", "Suavização",
        "Média ponderada dos vizinhos com pesos de uma gaussiana: pixels mais próximos pesam mais. "
        "Suaviza de forma mais natural que o Box e é a base de vários outros efeitos.",
        gaussian_blur,
        (Param("k", "Tamanho do kernel", "int", 9, 3, 61, 2, odd=True, short="k", help=K_HELP),
         Param("sigma", "Sigma (σ)", "float", 0.0, 0.0, 20.0, 0.5, short="σ",
               help="desvio-padrão da gaussiana; 0 faz o OpenCV calcular a partir do kernel.")),
    ),
    EffectSpec(
        "median", "Filtro da mediana", "Suavização",
        "Filtro não linear que troca cada pixel pela mediana da vizinhança. "
        "Excelente para remover ruído impulsivo (sal e pimenta) preservando melhor as bordas.",
        median_blur,
        (Param("k", "Tamanho do kernel", "int", 5, 3, 31, 2, odd=True, short="k", help=K_HELP),),
    ),
    EffectSpec(
        "bilateral", "Filtro bilateral (suaviza preservando bordas)", "Suavização",
        "Média ponderada pela distância espacial E pela diferença de cor: suaviza regiões "
        "homogêneas (efeito 'pele lisa' dos apps de beleza) sem borrar contornos fortes.",
        bilateral,
        (Param("d", "Diâmetro da vizinhança", "int", 9, 3, 15, 1, short="d",
               help="diâmetro em pixels da vizinhança considerada (valores altos ficam lentos no vídeo)."),
         Param("sigma_cor", "Sigma de cor", "float", 75, 10, 200, 5, short="σc",
               help="quanto maior, mais cores diferentes são misturadas."),
         Param("sigma_espaco", "Sigma espacial", "float", 75, 10, 200, 5, short="σe",
               help="quanto maior, mais longe a influência dos vizinhos.")),
    ),
    # --- Realce --------------------------------------------------------------
    EffectSpec(
        "sharpen", "Nitidez (Sharpen)", "Realce",
        "Convolução com kernel passa-alta [0 −a 0; −a 1+4a −a; 0 −a 0], que soma à imagem "
        "a diferença entre o pixel e seus vizinhos, deixando bordas e texturas mais marcadas.",
        sharpen,
        (Param("forca", "Força", "float", 1.0, 0.1, 4.0, 0.1, short="a",
               help="peso dos vizinhos no kernel; valores altos realçam ruído também."),),
    ),
    EffectSpec(
        "unsharp", "Máscara de nitidez (Unsharp Mask)", "Realce",
        "Técnica clássica de realce: subtrai da imagem uma versão desfocada dela "
        "(máscara = original − desfocada) e soma essa máscara multiplicada pela quantidade.",
        unsharp_mask,
        (Param("quantidade", "Quantidade", "float", 1.5, 0.0, 5.0, 0.1, short="q",
               help="quanto da máscara de detalhes é somado à imagem."),
         Param("sigma", "Raio (sigma)", "float", 3.0, 0.5, 15.0, 0.5, short="σ",
               help="tamanho dos detalhes realçados (sigma do desfoque gaussiano).")),
    ),
    EffectSpec(
        "laplacian", "Laplaciano (realce ou bordas)", "Realce",
        "Operador de segunda derivada (∇²f). No modo 'realce' faz g = f − c·∇²f, aumentando a nitidez; "
        "no modo 'bordas' mostra apenas a resposta do Laplaciano (contornos).",
        laplacian,
        (Param("modo", "Modo", "choice", "realce", choices=(("realce", "Realce (f − c·∇²f)"),
                                                            ("bordas", "Bordas (|∇²f|)")),
               short="modo", help="escolhe entre realçar a imagem ou mostrar só as bordas."),
         Param("ksize", "Abertura do kernel", "choice", "1",
               choices=(("1", "1 (3×3 clássico)"), ("3", "3"), ("5", "5")), short="ksize",
               help="tamanho da abertura usada pelo OpenCV para calcular as derivadas."),
         Param("ganho", "Ganho (c)", "float", 1.0, 0.1, 4.0, 0.1, short="c",
               help="multiplica a resposta do Laplaciano.")),
    ),
    # --- Bordas --------------------------------------------------------------
    EffectSpec(
        "sobel", "Sobel (gradiente)", "Bordas",
        "Calcula as derivadas de primeira ordem nas direções x e y com os kernels de Sobel e "
        "mostra a magnitude do gradiente, destacando bordas verticais e/ou horizontais.",
        sobel,
        (Param("direcao", "Direção", "choice", "xy",
               choices=(("xy", "Magnitude (x e y)"), ("x", "Somente x (bordas verticais)"),
                        ("y", "Somente y (bordas horizontais)")), short="dir",
               help="qual derivada é exibida."),
         Param("ksize", "Tamanho do kernel", "int", 3, 1, 7, 2, odd=True, short="k",
               help="1, 3, 5 ou 7."),
         Param("ganho", "Ganho", "float", 0.5, 0.05, 3.0, 0.05, short="g",
               help="multiplica a magnitude antes de converter para 8 bits.")),
    ),
    EffectSpec(
        "canny", "Detector de bordas de Canny", "Bordas",
        "Algoritmo de Canny: suavização, gradiente, supressão de não-máximos e histerese com dois "
        "limiares. Gera bordas finas e contínuas. Com 'fundo branco' vira um efeito de desenho.",
        canny,
        (Param("limiar_baixo", "Limiar baixo", "int", 60, 0, 255, 1, short="t1",
               help="gradientes abaixo dele nunca são borda."),
         Param("limiar_alto", "Limiar alto", "int", 150, 0, 255, 1, short="t2",
               help="gradientes acima dele são borda com certeza."),
         Param("espessura", "Espessura do traço", "int", 1, 1, 7, 1, short="esp",
               help="dilata as bordas para engrossar o traço."),
         Param("fundo_branco", "Fundo branco (desenho)", "bool", False, short="branco",
               help="inverte o resultado: traço preto sobre fundo branco.")),
    ),
    EffectSpec(
        "emboss", "Relevo (Emboss)", "Bordas",
        "Convolução com kernel direcional que simula iluminação lateral, dando aparência de "
        "relevo/gravura em metal.",
        emboss,
        (Param("estilo", "Estilo", "choice", "colorido",
               choices=(("colorido", "Relevo colorido"), ("cinza", "Relevo cinza (clássico)")),
               short="estilo", help="mantém as cores ou gera o relevo cinza tradicional."),
         Param("forca", "Força", "float", 1.0, 0.2, 4.0, 0.1, short="f",
               help="intensidade do relevo.")),
    ),
    # --- Cor e tom -----------------------------------------------------------
    EffectSpec(
        "grayscale", "Tons de cinza", "Cor e tom",
        "Converte a imagem para tons de cinza pela luminância: Y = 0,299·R + 0,587·G + 0,114·B.",
        grayscale,
    ),
    EffectSpec(
        "negative", "Negativo", "Cor e tom",
        "Inverte as intensidades: s = 255 − r. Áreas claras ficam escuras e as cores viram "
        "suas complementares.",
        negative,
    ),
    EffectSpec(
        "brightness_contrast", "Brilho e contraste", "Cor e tom",
        "Transformação linear ponto a ponto g = α·f + β, com saturação em [0, 255].",
        brightness_contrast,
        (Param("contraste", "Contraste (α)", "float", 1.25, 0.0, 3.0, 0.05, short="α",
               help="multiplica as intensidades (1 = sem mudança)."),
         Param("brilho", "Brilho (β)", "int", 15, -150, 150, 1, short="β",
               help="soma um valor a todas as intensidades.")),
    ),
    EffectSpec(
        "gamma", "Correção gama", "Cor e tom",
        "Transformação de potência s = 255·(r/255)^γ, aplicada com tabela (LUT). γ < 1 clareia "
        "as sombras; γ > 1 escurece os tons médios.",
        gamma_correction,
        (Param("gama", "Gama (γ)", "float", 0.6, 0.1, 5.0, 0.05, short="γ",
               help="expoente da curva."),),
    ),
    EffectSpec(
        "equalize", "Equalização de histograma", "Cor e tom",
        "Redistribui as intensidades para ocupar toda a faixa [0, 255], aumentando o contraste. "
        "Em imagens coloridas age só na luminância. CLAHE equaliza por blocos e limita o contraste.",
        equalize,
        (Param("metodo", "Método", "choice", "global",
               choices=(("global", "Global"), ("clahe", "CLAHE (adaptativa)")), short="método",
               help="equalização do histograma inteiro ou adaptativa por blocos."),
         Param("limite", "Limite de contraste (CLAHE)", "float", 2.0, 1.0, 10.0, 0.5, short="lim",
               help="só usado no CLAHE."),
         Param("blocos", "Grade de blocos (CLAHE)", "int", 8, 2, 16, 1, short="grade",
               help="número de blocos por lado; só usado no CLAHE.")),
    ),
    EffectSpec(
        "saturation", "Saturação", "Cor e tom",
        "Converte para HSV e multiplica o canal S (saturação): deixa as cores mais vivas ou "
        "mais apagadas. Não tem efeito em imagens de um canal.",
        saturation,
        (Param("fator", "Fator", "float", 1.5, 0.0, 3.0, 0.05, short="fator",
               help="0 = sem cor, 1 = original, >1 = cores mais intensas."),),
    ),
    EffectSpec(
        "temperature", "Temperatura de cor", "Cor e tom",
        "Aquece (mais vermelho, menos azul) ou esfria (mais azul) a imagem com curvas por canal, "
        "como os filtros 'quente'/'frio' dos stories. Não tem efeito em um canal só.",
        temperature,
        (Param("temperatura", "Temperatura", "int", 35, -100, 100, 1, short="t",
               help="positivo = quente, negativo = frio."),),
    ),
    EffectSpec(
        "sepia", "Sépia (foto antiga)", "Cor e tom",
        "Aplica uma matriz de cor que leva os tons para marrom/amarelado, imitando fotos antigas.",
        sepia,
        (Param("intensidade", "Intensidade", "float", 1.0, 0.0, 1.0, 0.05, short="int",
               help="mistura entre o original (0) e o sépia completo (1)."),),
    ),
    EffectSpec(
        "pseudocolor", "Pseudocor (mapa de cores)", "Cor e tom",
        "Converte para cinza e troca cada intensidade por uma cor de um mapa (colormap). "
        "Muito usado em imagens térmicas e médicas para destacar variações de intensidade.",
        pseudocolor,
        (Param("mapa", "Mapa de cores", "choice", "INFERNO", choices=COLORMAPS, short="mapa",
               help="paleta usada para colorir."),),
    ),
    EffectSpec(
        "threshold", "Limiarização (binarização)", "Segmentação",
        "Separa a imagem em preto e branco comparando cada pixel (em cinza) com um limiar. "
        "Otsu escolhe o limiar automaticamente; o adaptativo usa um limiar por vizinhança.",
        threshold,
        (Param("metodo", "Método", "choice", "binario",
               choices=(("binario", "Binário"), ("invertido", "Binário invertido"),
                        ("otsu", "Otsu (automático)"), ("adaptativo", "Adaptativo (gaussiano)")),
               short="método", help="forma de escolher o limiar."),
         Param("limiar", "Limiar", "int", 127, 0, 255, 1, short="T",
               help="usado nos métodos binário e invertido."),
         Param("bloco", "Tamanho do bloco (adaptativo)", "int", 15, 3, 51, 2, odd=True, short="bloco",
               help="vizinhança do limiar adaptativo."),
         Param("c", "Constante C (adaptativo)", "int", 5, -20, 20, 1, short="C",
               help="valor subtraído da média local.")),
    ),
    EffectSpec(
        "morphology", "Morfologia matemática", "Segmentação",
        "Operações morfológicas com elemento estruturante elíptico: erosão encolhe regiões claras, "
        "dilatação expande, abertura/fechamento removem ruídos/buracos e o gradiente mostra contornos.",
        morphology,
        (Param("operacao", "Operação", "choice", "dilatacao",
               choices=(("erosao", "Erosão"), ("dilatacao", "Dilatação"), ("abertura", "Abertura"),
                        ("fechamento", "Fechamento"), ("gradiente", "Gradiente morfológico"),
                        ("tophat", "Top-hat"), ("blackhat", "Black-hat")),
               short="op", help="operação morfológica aplicada."),
         Param("k", "Tamanho do elemento", "int", 5, 3, 31, 2, odd=True, short="k",
               help="diâmetro do elemento estruturante."),
         Param("iteracoes", "Iterações", "int", 1, 1, 10, 1, short="it",
               help="quantas vezes a operação é repetida.")),
    ),
    # --- Estilo --------------------------------------------------------------
    EffectSpec(
        "posterize", "Posterização", "Estilo",
        "Quantiza cada canal em poucos níveis de intensidade, criando áreas chapadas de cor "
        "(efeito pôster/pop-art).",
        posterize,
        (Param("niveis", "Níveis por canal", "int", 4, 2, 16, 1, short="níveis",
               help="quantidade de tons que sobram em cada canal."),),
    ),
    EffectSpec(
        "pixelate", "Pixelização (mosaico)", "Estilo",
        "Reduz a resolução (média por blocos) e amplia de volta sem interpolação, formando blocos.",
        pixelate,
        (Param("bloco", "Tamanho do bloco", "int", 12, 2, 80, 1, short="bloco",
               help="lado de cada bloco em pixels."),),
    ),
    EffectSpec(
        "vignette", "Vinheta", "Estilo",
        "Escurece gradualmente as bordas da imagem com uma máscara radial suave, "
        "chamando atenção para o centro (clássico dos filtros de story).",
        vignette,
        (Param("forca", "Força", "float", 0.7, 0.0, 1.0, 0.05, short="f",
               help="quanto os cantos escurecem (1 = preto)."),
         Param("raio", "Raio livre", "float", 0.35, 0.0, 0.9, 0.05, short="r",
               help="fração central que não é escurecida.")),
    ),
    EffectSpec(
        "cartoon", "Cartoon (desenho animado)", "Estilo",
        "Combina filtro bilateral repetido + posterização (cores chapadas) com bordas obtidas "
        "por limiarização adaptativa, imitando um desenho.",
        cartoon,
        (Param("suavizacao", "Passadas de suavização", "int", 2, 1, 5, 1, short="pass",
               help="quantas vezes o bilateral é aplicado (mais = mais lento)."),
         Param("cores", "Níveis de cor", "int", 8, 2, 16, 1, short="cores",
               help="níveis por canal na posterização."),
         Param("bordas", "Tamanho das bordas", "int", 9, 3, 21, 2, odd=True, short="bordas",
               help="vizinhança da limiarização adaptativa (traço).")),
    ),
    # --- Ruído ---------------------------------------------------------------
    EffectSpec(
        "noise", "Adicionar ruído", "Ruído",
        "Acrescenta ruído artificial (gaussiano ou sal e pimenta) — útil para testar os filtros "
        "de suavização (ex.: ruído sal e pimenta + filtro da mediana).",
        add_noise,
        (Param("tipo", "Tipo de ruído", "choice", "sal_pimenta",
               choices=(("sal_pimenta", "Sal e pimenta"), ("gaussiano", "Gaussiano")), short="tipo",
               help="distribuição do ruído."),
         Param("quantidade", "Quantidade", "float", 20.0, 0.0, 100.0, 1.0, short="q",
               help="gaussiano: desvio-padrão; sal e pimenta: 100 = 25% dos pixels."),
         Param("semente", "Semente aleatória", "int", 42, 0, 9999, 1, short="seed",
               help="mesma semente gera sempre o mesmo ruído.")),
    ),
)

FILTERS_BY_KEY: dict[str, EffectSpec] = {f.key: f for f in FILTERS}

CATEGORY_ORDER = ("Suavização", "Realce", "Bordas", "Cor e tom", "Segmentação", "Estilo",
                  "Ruído")


def filters_by_category() -> list[tuple[str, list[EffectSpec]]]:
    groups: dict[str, list[EffectSpec]] = {c: [] for c in CATEGORY_ORDER}
    for spec in FILTERS:
        groups.setdefault(spec.category, []).append(spec)
    return [(c, specs) for c, specs in groups.items() if specs]
