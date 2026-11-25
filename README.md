# PG Stories — editor de imagens e vídeo com filtros e stickers

Trabalho do **Grau B** da disciplina **Processamento Gráfico: Fundamentos** (Unisinos — Escola Politécnica, 2026/2).

Protótipo de um aplicativo de edição de imagens e vídeo inspirado nos *stories* do Instagram, com foco em
técnicas de **processamento de imagens**: filtros de suavização e realce, seleção de canais, operações
aritméticas entre duas imagens e stickers com transparência, inclusive animados.

**Professora:** Rossana Baptista Queiroz · **Autores:** Fábio Silveira e Pedro Scott

![Interface do PG Stories com filtros e stickers aplicados](docs/tela_stickers.jpg)

---

## Sumário

- [Requisitos do enunciado × implementação](#requisitos-do-enunciado--implementação)
- [Relação com o conteúdo da disciplina](#relação-com-o-conteúdo-da-disciplina)
- [Como executar](#como-executar)
- [Como usar](#como-usar)
- [Filtros](#filtros-26)
- [Seleção de canais](#seleção-de-canais)
- [Operações com duas imagens](#operações-com-duas-imagens-7)
- [Stickers](#stickers-11)
- [Extras implementados](#extras-implementados)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Detalhes de implementação](#detalhes-de-implementação)
- [Testes](#testes)
- [Problemas comuns](#problemas-comuns)
- [Referências e créditos](#referências-e-créditos)

---

## Requisitos do enunciado × implementação

| Requisito | Onde / como |
|---|---|
| **Modo Foto**: carregar imagem do disco | Botão **Abrir foto** (Ctrl+O), menu **Exemplos** ou arrastar o arquivo para a janela |
| **Modo Vídeo**: webcam em tempo real | Botão **Iniciar/Parar webcam** (Ctrl+K), com escolha do índice da câmera e da resolução. Também abre **arquivos de vídeo** (útil sem webcam) |
| Filtros, operações e stickers nos dois modos | O mesmo *pipeline* de efeitos é aplicado à foto ou a cada quadro do vídeo |
| **Salvar** imagem resultante / frame do vídeo | Botão **Salvar** (Ctrl+S) — no vídeo salva o quadro do momento do clique |
| **Resetar** (voltar à imagem original) | Botão **Resetar** (Ctrl+R); há também **Desfazer** (Ctrl+Z) |
| **≥ 10 filtros** (com suavização e realce) | **26 filtros** em 7 categorias, incluindo 4 de suavização e 3 de realce |
| **Seleção de canais** (imagem inteira RGB/cinza ou só R, G ou B) | Seletor *"Onde aplicar"* em cada filtro/operação; com um canal escolhido a imagem principal exibe só aquele canal |
| **≥ 3 operações aritméticas** com duas imagens | **7 operações**: adição e subtração ponderadas, diferença absoluta, blending, multiplicação, máximo e mínimo |
| **Descrição do filtro antes de aplicar** | Ao selecionar um filtro aparece a descrição e a lista de parâmetros **na interface e no console** — ele só é aplicado ao clicar em **Aplicar** |
| **≥ 5 stickers** com canal alfa, posicionados com o mouse | **11 stickers** PNG com transparência (8 estáticos + 3 animados); clique para colar, arraste para mover, botão direito para remover |
| Interface (console/teclado ou mista) | Interface gráfica completa em **Qt (PySide6)** + mensagens no console |
| Tecnologias | **Python + OpenCV** (e NumPy) |

**Extras (opcionais) implementados:** interface gráfica com biblioteca externa (Qt), combinação de filtros
em sequência e stickers animados por *spritesheet* — detalhes em [Extras implementados](#extras-implementados).

---

## Relação com o conteúdo da disciplina

Os recursos do projeto foram construídos a partir dos conteúdos do plano de ensino e das referências do
enunciado (Gonzalez & Woods e a documentação oficial do OpenCV):

| Aula (plano de ensino) | Onde aparece no projeto |
|---|---|
| Transformações em objetos (semanas 6 e 7) | Escala, rotação e translação dos stickers (`cv2.resize`, `cv2.getRotationMatrix2D` + `cv2.warpAffine`) |
| Camadas e animação de sprites (semana 9) | Stickers como camadas com canal alfa sobre a imagem; stickers animados por *spritesheet*, com quadro = ⌊t·fps⌋ mod n |
| Sistemas de Cores (semana 11) | Canais R, G e B (seleção de canais), tons de cinza pela luminância, HSV (saturação), YCrCb (equalização só da luminância), negativo, sépia, temperatura de cor e pseudocor |
| Introdução ao Processamento de Imagens (semana 12) | Operações pontuais: brilho e contraste, correção gama, limiarização (binária, Otsu, adaptativa), posterização (redução de níveis de intensidade), equalização de histograma; operações aritméticas entre duas imagens |
| Processamento de Imagens: OpenCV (semana 13) | Leitura e gravação de imagens, captura da webcam (`cv2.VideoCapture`), conversões de espaço de cor, redimensionamento (pixelização), `cv2.add` / `cv2.addWeighted` |
| Processamento de Imagens: filtros (semana 14) | Convolução com kernels: box, gaussiano, mediana, bilateral, nitidez, unsharp mask, Laplaciano, Sobel e relevo (`cv2.filter2D`); morfologia (erosão, dilatação…); ruído gaussiano e sal e pimenta para testar a suavização; vinheta (multiplicação por máscara); cartoon (combinação de filtros) |
| Introdução à Visão Computacional (semana 15) | Detector de bordas de Canny |

A única parte que vai além do conteúdo das aulas é a **interface em Qt (PySide6)**: ela está no projeto
porque o enunciado lista *"Interface Gráfica com biblioteca externa (ex.: Qt, Dear ImGui, Tkinter)"* como
extra. Todo o processamento de imagens é feito só com OpenCV e NumPy.

---

## Como executar

Requisitos: **Python 3.10 ou superior** (testado com 3.13) e uma webcam para o modo vídeo (opcional).

> Sem o git instalado: na página do repositório no GitHub, clique em **Code → Download ZIP**, descompacte
> e abra o terminal dentro da pasta descompactada (a que tem o `main.py`).

### Linux

```bash
git clone <URL-deste-repositório>
cd <pasta-do-repositório>
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Windows (PowerShell)

```powershell
git clone <URL-deste-repositório>
cd <pasta-do-repositório>
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

> Se o PowerShell bloquear o `Activate.ps1`, rode antes
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` ou use o `cmd` com `.venv\Scripts\activate.bat`.

### Opções de linha de comando

```bash
python main.py                                 # abre a interface vazia
python main.py assets/exemplos/gato.jpg        # já abre uma foto (Modo Foto)
python main.py --webcam                        # já inicia a webcam 0 (Modo Vídeo)
python main.py --webcam 1                      # usa a câmera de índice 1
python main.py --video caminho/do/video.mp4    # Modo Vídeo a partir de um arquivo
```

---

## Como usar

A janela tem a **imagem à esquerda** e um **painel com quatro abas** à direita.

![Aba de filtros com a descrição do filtro selecionado](docs/tela_filtros.jpg)

1. **Escolha a fonte**: *Abrir foto*, *Exemplos* (fotos que acompanham o projeto), *Iniciar webcam* ou
   *Abrir vídeo*. O selo no canto superior direito mostra o modo atual (**MODO FOTO** / **MODO VÍDEO**).
2. **Aba Filtros**: selecione um filtro na lista → leia a **descrição e os parâmetros** → ajuste os controles →
   escolha **onde aplicar** (imagem inteira RGB, tons de cinza ou um único canal) → **Aplicar filtro**.
   Marque *Prévia ao vivo* para ver o resultado antes de aplicar.
3. **Aba Operações**: escolha a **imagem B** (texturas prontas, outra foto do disco ou *"Usar imagem atual
   como B"*), escolha a operação, ajuste os parâmetros e clique em **Aplicar operação**.
4. **Aba Stickers**: selecione um sticker, ajuste tamanho e rotação e **clique na imagem** para colar.
   Arraste um sticker colado para movê-lo; clique com o **botão direito** sobre ele para removê-lo.
5. **Aba Pipeline**: lista dos efeitos aplicados, na ordem. Dá para **subir/descer**, **remover** um passo ou
   **desfazer** o último.
6. **Salvar** grava a imagem exibida (com filtros e stickers) em PNG/JPG/BMP. Por padrão sugere a pasta
   `saidas/` do projeto. **Resetar** remove tudo e volta à imagem original.

Ao **parar a webcam**, o último quadro vira uma foto editável (Modo Foto), o que facilita colar stickers com
calma e salvar.

### Atalhos

| Atalho | Ação |
|---|---|
| `Ctrl+O` | Abrir foto |
| `Ctrl+K` | Iniciar / parar webcam |
| `Ctrl+Shift+O` | Abrir arquivo de vídeo |
| `Ctrl+S` | Salvar imagem / quadro atual |
| `Ctrl+Z` | Desfazer o último filtro, operação ou sticker |
| `Ctrl+R` | Resetar (voltar à imagem original) |
| Botão *Ver original (segure)* | Mostra a imagem sem efeitos enquanto estiver pressionado |
| Clique esquerdo na imagem | Colar o sticker selecionado / arrastar um sticker |
| Clique direito num sticker | Remover o sticker |

### Mensagens no console

O terminal em que o programa foi aberto mostra a descrição de cada filtro/operação **no momento em que é
selecionado** (antes de aplicar), além do histórico do pipeline:

```text
======================================================================
Filtro selecionado (ainda não aplicado):
[Realce] Máscara de nitidez (Unsharp Mask)
  Técnica clássica de realce: subtrai da imagem uma versão desfocada dela (máscara = original − desfocada)
  e soma essa máscara multiplicada pela quantidade.
  Parâmetros configuráveis:
   - Quantidade (0 a 5; padrão: 1.5): quanto da máscara de detalhes é somado à imagem.
   - Raio (sigma) (0.5 a 15; padrão: 3): tamanho dos detalhes realçados (sigma do desfoque gaussiano).
[pipeline] + Máscara de nitidez (Unsharp Mask)  (q=1.5, σ=3)  · RGB
```

---

## Filtros (26)

| # | Categoria | Filtro | Parâmetros configuráveis |
|---|---|---|---|
| 1 | Suavização | Desfoque de caixa (Box / média) | Tamanho do kernel |
| 2 | Suavização | Desfoque gaussiano (Gaussian Blur) | Tamanho do kernel, Sigma (σ) |
| 3 | Suavização | Filtro da mediana | Tamanho do kernel |
| 4 | Suavização | Filtro bilateral (suaviza preservando bordas) | Diâmetro da vizinhança, Sigma de cor, Sigma espacial |
| 5 | Realce | Nitidez (Sharpen) | Força |
| 6 | Realce | Máscara de nitidez (Unsharp Mask) | Quantidade, Raio (sigma) |
| 7 | Realce | Laplaciano (realce ou bordas) | Modo, Abertura do kernel, Ganho (c) |
| 8 | Bordas | Sobel (gradiente) | Direção, Tamanho do kernel, Ganho |
| 9 | Bordas | Detector de bordas de Canny | Limiar baixo, Limiar alto, Espessura do traço, Fundo branco |
| 10 | Bordas | Relevo (Emboss) | Estilo, Força |
| 11 | Cor e tom | Tons de cinza | — |
| 12 | Cor e tom | Negativo | — |
| 13 | Cor e tom | Brilho e contraste | Contraste (α), Brilho (β) |
| 14 | Cor e tom | Correção gama | Gama (γ) |
| 15 | Cor e tom | Equalização de histograma (global ou CLAHE) | Método, Limite de contraste, Grade de blocos |
| 16 | Cor e tom | Saturação | Fator |
| 17 | Cor e tom | Temperatura de cor | Temperatura |
| 18 | Cor e tom | Sépia (foto antiga) | Intensidade |
| 19 | Cor e tom | Pseudocor (mapa de cores) | Mapa de cores |
| 20 | Segmentação | Limiarização (binário, invertido, Otsu, adaptativo) | Método, Limiar, Tamanho do bloco, Constante C |
| 21 | Segmentação | Morfologia matemática | Operação, Tamanho do elemento, Iterações |
| 22 | Estilo | Posterização | Níveis por canal |
| 23 | Estilo | Pixelização (mosaico) | Tamanho do bloco |
| 24 | Estilo | Vinheta | Força, Raio livre |
| 25 | Estilo | Cartoon (desenho animado) | Passadas de suavização, Níveis de cor, Tamanho das bordas |
| 26 | Ruído | Adicionar ruído (sal e pimenta ou gaussiano) | Tipo, Quantidade, Semente |

A descrição completa de cada filtro e de cada parâmetro está no próprio código
([`pgstories/filters.py`](pgstories/filters.py)) e é exibida pelo programa ao selecionar o filtro.

![Galeria com todos os filtros aplicados à foto de exemplo](docs/galeria_filtros.jpg)

> Dica para testar a suavização: aplique **Adicionar ruído → Sal e pimenta** e depois **Filtro da mediana**
> (remove quase todo o ruído) e compare com o **Desfoque de caixa** (que só espalha o ruído).

---

## Seleção de canais

Cada filtro (e cada operação) pode ser aplicado:

- na **imagem inteira colorida (RGB)** — padrão;
- na **imagem inteira em tons de cinza**;
- **somente no canal R, G ou B** — o efeito é aplicado só naquele canal e **a imagem principal passa a
  exibir o resultado desse canal**, na cor do canal ou em tons de cinza (opção *"Canal isolado na cor do
  canal"*).

![Equalização de histograma aplicada só no canal R](docs/tela_canal_r.jpg)

![Desfoque gaussiano aplicado em cada modo de canal](docs/galeria_canais.jpg)

---

## Operações com duas imagens (7)

A **imagem A** é a imagem atual (foto ou quadro da webcam, já com os efeitos anteriores) e a **imagem B** é
escolhida na aba Operações. B é ajustada automaticamente ao tamanho de A (preenchendo e recortando o centro,
ou esticando). Os resultados são saturados em [0, 255].

| Operação | Fórmula | Parâmetros |
|---|---|---|
| Adição ponderada | `A·wA + B·wB` | Peso de A, Peso de B |
| Subtração ponderada | `A·wA − B·wB + d` | Peso de A, Peso de B, Deslocamento |
| Diferença absoluta | `ganho · \|A − B\|` | Ganho |
| Blending (mistura alfa) | `(1 − α)·A + α·B` | Alfa |
| Multiplicação | `A·B / 255` | Intensidade |
| Máximo (clarear) | `max(A, B)` | — |
| Mínimo (escurecer) | `min(A, B)` | — |

Texturas prontas para usar como B ficam em [`assets/texturas`](assets/texturas): *luz_quente* (light leak),
*bokeh*, *por_do_sol*, *papel_antigo* e *moldura* (com **Máximo** + *Esticar* vira uma borda de polaroid).
Na webcam, **"Usar imagem atual como B" + Diferença absoluta** mostra só o que se moveu na cena.

![Galeria das operações entre duas imagens](docs/galeria_operacoes.jpg)

---

## Stickers (11)

Todos os stickers são PNG com **canal alfa** (transparência), desenhados por código para este trabalho
([`tools/gerar_assets.py`](tools/gerar_assets.py)):

- **Estáticos (8):** estrela, coração, óculos escuros, coroa, bigode, balão "UAU!", orelhas de gato e arco-íris.
- **Animados (3):** coração pulsante (8 quadros), estrela girando (12 quadros) e brilhos (12 quadros), em
  ***spritesheet*** horizontal.

Cada sticker tem um arquivo `.json` ao lado com nome, descrição e — nos animados — o número de quadros
e a velocidade (fps). Para **adicionar um sticker novo** basta copiar um PNG com
transparência para `assets/stickers/` (o `.json` é opcional).

```json
{ "nome": "Coração pulsante", "descricao": "Coração batendo (spritesheet com 8 quadros).",
  "frames": 8, "cols": 8, "rows": 1, "fps": 10 }
```

Os stickers funcionam no Modo Foto e também no Modo Vídeo (as posições são guardadas em coordenadas
relativas à imagem).

---

## Extras implementados

| Extra | Como foi feito |
|---|---|
| **Interface gráfica com biblioteca externa** | Interface em **Qt 6 (PySide6)**: lista de filtros por categoria, painel de descrição, controles de parâmetros gerados automaticamente, prévia ao vivo, prévia do sticker seguindo o mouse, arrastar e soltar arquivos, tema escuro |
| **Combinação de filtros** | *Pipeline* não destrutivo: cada filtro/operação é aplicado sobre o resultado do anterior; os passos podem ser reordenados, removidos ou desfeitos (aba Pipeline) |
| **Stickers animados** | Spritesheets em `assets/stickers/*.png` + metadados em `.json`; o quadro exibido depende do tempo (`quadro = ⌊t·fps⌋ mod n`) |

---

## Estrutura do projeto

```text
.
├── main.py                    # ponto de entrada (abre a interface)
├── requirements.txt           # dependências para executar
├── requirements-dev.txt       # + pytest e Pillow (testes e scripts de tools/)
├── pgstories/                 # código do aplicativo
│   ├── params.py              # descrição de parâmetros e efeitos (nome, descrição, faixa de valores)
│   ├── filters.py             # os 26 filtros
│   ├── operations.py          # as 7 operações com duas imagens
│   ├── pipeline.py            # sequência de efeitos + seleção de canais
│   ├── stickers.py            # carga de stickers, spritesheets e composição com alfa
│   ├── video.py               # webcam / arquivo de vídeo
│   ├── io_utils.py            # leitura/gravação de imagens (aceita caminhos com acento)
│   ├── paths.py               # caminhos das pastas
│   └── gui/                   # interface Qt (janela principal, visualizador, widgets, tema)
├── assets/
│   ├── stickers/              # 11 stickers PNG com alfa + .json
│   ├── texturas/              # imagens B prontas para as operações
│   ├── exemplos/              # fotos de exemplo
├── tests/test_core.py         # testes automatizados do núcleo
├── tools/                     # scripts que geram stickers, texturas, galerias e capturas de tela
└── docs/                      # imagens usadas neste README
```

O **núcleo de processamento** (`filters`, `operations`, `pipeline`, `stickers`, `video`) não depende da
interface: pode ser usado e testado sem abrir janelas.

---

## Detalhes de implementação

- **Descrição dos efeitos como dados.** Cada filtro/operação é um `EffectSpec` com nome, categoria, descrição,
  lista de `Param` (tipo, faixa, padrão, ajuda) e a função que processa. A interface monta os controles a
  partir disso e o mesmo texto é mostrado no painel e no console.
- **Pipeline não destrutivo.** A imagem original nunca é alterada; o resultado é sempre recalculado a partir
  dela aplicando a lista de passos. Por isso *Resetar* e *Desfazer* são exatos e o mesmo pipeline vale para
  a foto e para cada quadro da webcam.
- **Seleção de canais.** Antes de cada passo a imagem é convertida para o formato do modo escolhido
  (BGR, cinza ou um canal isolado); depois o resultado volta a ser BGR para exibição — no modo canal, só o
  canal processado é exibido.
- **Kernels.** Tamanhos de janela são forçados a valores ímpares; filtros lineares usam `cv2.filter2D`,
  `cv2.GaussianBlur`, `cv2.blur` etc., e os que geram valores negativos (Laplaciano, Sobel) são calculados em
  `float32` antes de voltar a 8 bits.
- **Stickers e alfa.** `resultado = α·sticker + (1 − α)·fundo`, recortando o sticker quando ele passa da borda
  da imagem. Redimensionamento e rotação ficam em cache para o vídeo continuar fluido.
- **Caminhos com acento.** `cv2.imread`/`cv2.imwrite` falham no Windows com caminhos como
  `C:\Users\...\Área de Trabalho`; por isso a leitura/gravação usa `np.fromfile` + `cv2.imdecode` e
  `cv2.imencode` + `tofile`.
- **Fotos grandes** são reduzidas para no máximo 1920 px no maior lado, para a prévia continuar interativa.

---

## Testes

```bash
pip install -r requirements-dev.txt
python -m pytest                 # testes do núcleo (todos os efeitos em todos os modos de canal, etc.)
python tools/capturas_de_tela.py # teste da interface sem janela (gera as imagens de docs/)
```

---

## Problemas comuns

| Problema | Solução |
|---|---|
| `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"` (Linux) | Verifique se o pacote `opencv-python` (não *headless*) está instalado no mesmo ambiente: `pip uninstall opencv-python` e mantenha só o `opencv-python-headless`. Em sessões Wayland também dá para forçar `QT_QPA_PLATFORM=wayland python main.py` |
| A webcam não abre | Feche outros programas que usam a câmera, tente outro índice no campo **Câmera** ou outra resolução. No Linux o usuário precisa ter acesso a `/dev/video*` |
| Vídeo lento | Escolha **640 × 480** na resolução da câmera e evite muitos filtros pesados (bilateral, cartoon) ao mesmo tempo |

---

## Referências e créditos

- GONZALEZ, Rafael C.; WOODS, Richard E. *Digital image processing*. 4th ed. Noida: Pearson, c2018.
- Material das aulas de Processamento Gráfico: Fundamentos (Unisinos, 2026/2), conforme o plano de ensino.
- Documentação oficial do OpenCV: <https://docs.opencv.org/4.x/>
- Qt for Python (PySide6): <https://doc.qt.io/qtforpython-6/>
- Fotos de exemplo (`assets/exemplos`): *gato* (Stefan van der Walt, CC0), *café* (Rachel Michetti, CC0) e
  *foguete* (SpaceX, domínio público), distribuídas com a biblioteca scikit-image.
- Stickers e texturas: criados por código para este trabalho (`tools/gerar_assets.py`).
