"""
Painel do Salvamento Automático
-------------------------------
Como usar: python painel_salvamento.py

Abas:
  1) IDs          -> cadastra IDs em lotes de 10 e define o comentário único
  2) Coordenadas  -> captura (ou digita) os pontos de clique
  3) Executar     -> checklist + botão que roda a automação

Tudo é salvo em JSON na pasta "dados" ao lado deste arquivo
(funciona em qualquer letra de unidade do pendrive).
"""

import json
import math
import os
import re
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

import pyautogui as pa
import pyperclip

try:
    import winsound  # só existe no Windows
except ImportError:
    winsound = None


# =========================
# Caminhos (relativos ao arquivo, não à letra do pendrive)
# =========================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DADOS_DIR = os.path.join(BASE_DIR, "dados")
ARQ_DADOS = os.path.join(DADOS_DIR, "dados.json")
ARQ_COORD = os.path.join(DADOS_DIR, "coordenadas.json")
ARQ_LOG = os.path.join(DADOS_DIR, "log.txt")

os.makedirs(DADOS_DIR, exist_ok=True)

TAM_LOTE = 10
SEGUNDOS_CAPTURA = 5

# =========================
# Passos do ciclo (chave, nome amigável, coordenada padrão)
# Os padrões vêm do script original; None = ainda precisa capturar
# (eram os cliques por reconhecimento de imagem).
# =========================

PASSOS = [
    ("campo_localizar_id", "1. Localizar ID", (610, 444)),
    ("btn_anexo", "2. Botão Anexo", None),
    ("campo_comentario", "3. Campo Comentário", (445, 416)),
    ("btn_selecionar_doc", "4. Selecionar documento", (405, 503)),
    ("arquivo_na_janela", "5. Arquivo na janela", (288, 389)),
    ("area_neutra", "6. Área neutra (foco da página)", (300, 300)),
    ("btn_salvar", "7. Botão Salvar (após rolar)", None),
    ("barra_pasta", "8. Pasta na barra de tarefas", (656, 746)),
    ("arquivo_excluir", "9. Arquivo a excluir (pasta)", (282, 232)),
    ("barra_navegador", "10. Navegador na barra de tarefas", (705, 742)),
    ("menu_cadastros", "11. Menu Cadastros", None),
    ("btn_voltar_localizar", "12. Botão Localizar Cadastros", None),
]

CHECKLIST = [
    "Navegador aberto, logado e na tela Localizar ID",
    "Pasta SALVAR_ARQUIVO aberta em tela cheia, com o documento",
    "Coordenadas capturadas e conferidas (aba Coordenadas)",
    "Sei interromper: mover o mouse para o canto superior esquerdo",
]

# =========================
# Visual (tema escuro)
# =========================

BG = "#0b0b0f"
CARD = "#14141a"
CAMPO = "#000000"
BORDA = "#2a2a33"
TXT = "#f2f2f5"
SUB = "#9a9aa5"
AZUL = "#3b82f6"
VERDE = "#22c55e"
LARANJA = "#f59e0b"
VERMELHO = "#ef4444"
FONTE = ("Segoe UI", 10)
FONTE_B = ("Segoe UI", 10, "bold")


def campo(pai, largura=16):
    return tk.Entry(
        pai, width=largura, bg=CAMPO, fg=TXT, insertbackground=TXT,
        relief="flat", highlightthickness=1, highlightbackground=BORDA,
        highlightcolor=AZUL, font=("Segoe UI", 11),
    )


def botao(pai, texto, comando, cor=AZUL, **kw):
    return tk.Button(
        pai, text=texto, command=comando, bg=cor, fg="white",
        activebackground=cor, activeforeground="white", relief="flat",
        font=FONTE_B, padx=12, pady=6, cursor="hand2", **kw,
    )


def rotulo(pai, texto, fonte=FONTE, cor=TXT, **kw):
    return tk.Label(pai, text=texto, bg=pai["bg"], fg=cor, font=fonte, **kw)


def cartao(pai):
    return tk.Frame(
        pai, bg=CARD, padx=16, pady=14,
        highlightthickness=1, highlightbackground=BORDA,
    )


# =========================
# JSON
# =========================

def ler_json(caminho, padrao):
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return padrao


def gravar_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)


# =========================
# Aplicação
# =========================

class App:
    def __init__(self):
        dados = ler_json(ARQ_DADOS, {})
        self.ids = sorted(
            {str(i) for i in dados.get("ids", []) if str(i).isdigit()},
            key=int,
        )
        comentario = dados.get("comentario", "DOCUMENTOS 2026")
        pausa = dados.get("pausa", 5.0)
        self.coord_salvas = ler_json(ARQ_COORD, {})

        self.janela = tk.Tk()
        self.janela.title("Salvamento Automático")
        self.janela.geometry("860x700")
        self.janela.minsize(860, 700)
        self.janela.configure(bg=BG)
        self.janela.protocol("WM_DELETE_WINDOW", self.fechar)

        # Barra de abas
        barra = tk.Frame(self.janela, bg=BG)
        barra.pack(fill="x", padx=14, pady=(12, 8))
        self.btn_abas = {}
        self.paginas = {}
        for nome, titulo in (
            ("ids", "IDs"),
            ("coord", "Coordenadas"),
            ("exec", "Executar"),
        ):
            b = tk.Button(
                barra, text=titulo, command=lambda n=nome: self.mostrar(n),
                relief="flat", font=FONTE_B, padx=18, pady=6,
                cursor="hand2", bd=0,
            )
            b.pack(side="left", padx=(0, 6))
            self.btn_abas[nome] = b

        area = tk.Frame(self.janela, bg=BG)
        area.pack(fill="both", expand=True)
        for nome in self.btn_abas:
            self.paginas[nome] = tk.Frame(area, bg=BG)

        self.montar_aba_ids(self.paginas["ids"], comentario)
        self.montar_aba_coord(self.paginas["coord"])
        self.montar_aba_exec(self.paginas["exec"], pausa)

        self.refresh_lista()
        self.mostrar("ids")

    # ---------- navegação ----------

    def mostrar(self, nome):
        for n, frame in self.paginas.items():
            frame.pack_forget()
            ativo = n == nome
            self.btn_abas[n].configure(
                bg=AZUL if ativo else CARD,
                fg="white" if ativo else SUB,
                activebackground=AZUL if ativo else CARD,
                activeforeground="white",
            )
        self.paginas[nome].pack(fill="both", expand=True, padx=14, pady=(0, 14))
        if nome == "exec":
            self.atualizar_resumo()

    # ---------- aba IDs ----------

    def montar_aba_ids(self, pai, comentario):
        pai.columnconfigure(0, weight=3)
        pai.columnconfigure(1, weight=2)
        pai.rowconfigure(0, weight=1)

        esq = cartao(pai)
        esq.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        esq.columnconfigure(0, weight=1)
        esq.columnconfigure(1, weight=1)

        rotulo(esq, "Cadastro de IDs", ("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w")
        rotulo(esq, "Adicionar até 10 IDs", FONTE_B).grid(
            row=1, column=0, sticky="w", pady=(6, 0))
        rotulo(esq, "10 registros por lote", ("Segoe UI", 9, "bold"), AZUL).grid(
            row=1, column=1, sticky="e", pady=(6, 0))

        self.entradas = []
        for i in range(TAM_LOTE):
            r = 2 + (i // 2) * 2
            c = i % 2
            px = (0, 8) if c == 0 else (8, 0)
            rotulo(esq, f"Registro {i + 1}", ("Segoe UI", 9, "bold"), SUB).grid(
                row=r, column=c, sticky="w", padx=px, pady=(8, 0))
            e = campo(esq)
            e.grid(row=r + 1, column=c, sticky="ew", padx=px, ipady=5)
            e.bind("<Return>", lambda ev, k=i: self.proximo_campo(k))
            self.entradas.append(e)

        rotulo(esq, "Comentário único", FONTE_B).grid(
            row=12, column=0, columnspan=2, sticky="w", pady=(14, 0))
        self.campo_comentario = campo(esq, 40)
        self.campo_comentario.insert(0, comentario)
        self.campo_comentario.grid(
            row=13, column=0, columnspan=2, sticky="ew", ipady=5, pady=(4, 0))
        self.campo_comentario.bind("<FocusOut>", lambda e: self.salvar_dados())

        botoes = tk.Frame(esq, bg=CARD)
        botoes.grid(row=14, column=0, columnspan=2, sticky="w", pady=(14, 0))
        botao(botoes, "Adicionar lote à lista", self.adicionar_lote, AZUL).pack(
            side="left")
        botao(botoes, "Limpar campos", self.limpar_campos, "#3f3f4a").pack(
            side="left", padx=8)

        self.status_ids = rotulo(esq, "", ("Segoe UI", 9), SUB)
        self.status_ids.grid(row=15, column=0, columnspan=2, sticky="w", pady=(8, 0))

        # Lista à direita
        dir_ = cartao(pai)
        dir_.grid(row=0, column=1, sticky="nsew")
        dir_.rowconfigure(2, weight=1)
        dir_.columnconfigure(0, weight=1)

        rotulo(dir_, "IDs salvos", ("Segoe UI", 14, "bold")).grid(
            row=0, column=0, sticky="w")
        self.lbl_contagem = rotulo(dir_, "", ("Segoe UI", 9), SUB)
        self.lbl_contagem.grid(row=1, column=0, sticky="w", pady=(2, 8))

        moldura = tk.Frame(dir_, bg=CARD)
        moldura.grid(row=2, column=0, sticky="nsew")
        moldura.rowconfigure(0, weight=1)
        moldura.columnconfigure(0, weight=1)
        self.lista = tk.Listbox(
            moldura, bg=CAMPO, fg=TXT, selectbackground=AZUL,
            selectforeground="white", font=("Consolas", 11),
            relief="flat", highlightthickness=1, highlightbackground=BORDA,
            activestyle="none", selectmode=tk.EXTENDED,
        )
        self.lista.grid(row=0, column=0, sticky="nsew")
        barra = tk.Scrollbar(moldura, command=self.lista.yview)
        barra.grid(row=0, column=1, sticky="ns")
        self.lista.configure(yscrollcommand=barra.set)

        bt = tk.Frame(dir_, bg=CARD)
        bt.grid(row=3, column=0, sticky="w", pady=(10, 0))
        botao(bt, "Remover selecionados", self.remover_selecionados, "#3f3f4a").pack(
            side="left")
        botao(bt, "Limpar lista", self.limpar_lista, VERMELHO).pack(
            side="left", padx=8)

    def proximo_campo(self, k):
        if k + 1 < TAM_LOTE:
            self.entradas[k + 1].focus_set()
        else:
            self.adicionar_lote()

    def limpar_campos(self):
        for e in self.entradas:
            e.delete(0, tk.END)
        self.entradas[0].focus_set()

    def adicionar_lote(self):
        # Aceita colar vários IDs de uma vez em qualquer campo
        # (separados por espaço, vírgula ou ponto e vírgula).
        textos = []
        for e in self.entradas:
            textos += re.split(r"[\s,;]+", e.get().strip())
        novos = [t for t in textos if t]

        if not novos:
            self.status_ids.configure(text="Digite ao menos um ID.", fg=LARANJA)
            return

        invalidos = [t for t in novos if not t.isdigit()]
        if invalidos:
            messagebox.showerror(
                "ID inválido",
                "Use somente números. Corrija:\n\n" + "\n".join(invalidos),
            )
            return

        adicionados, repetidos = [], []
        for t in novos:
            if t in self.ids or t in adicionados:
                repetidos.append(t)
            else:
                adicionados.append(t)

        self.ids = sorted(self.ids + adicionados, key=int)
        self.salvar_dados()
        self.refresh_lista()
        self.limpar_campos()

        msg = f"{len(adicionados)} ID(s) adicionado(s)."
        if repetidos:
            msg += f" {len(repetidos)} repetido(s) ignorado(s)."
        self.status_ids.configure(text=msg, fg=VERDE)

    def remover_selecionados(self):
        marcados = {self.lista.get(i) for i in self.lista.curselection()}
        if not marcados:
            return
        self.ids = [i for i in self.ids if i not in marcados]
        self.salvar_dados()
        self.refresh_lista()

    def limpar_lista(self):
        if not self.ids:
            return
        if messagebox.askyesno("Limpar lista", f"Apagar os {len(self.ids)} IDs salvos?"):
            self.ids = []
            self.salvar_dados()
            self.refresh_lista()

    def refresh_lista(self):
        self.lista.delete(0, tk.END)
        for i in self.ids:
            self.lista.insert(tk.END, i)
        total = len(self.ids)
        lotes = math.ceil(total / TAM_LOTE)
        self.lbl_contagem.configure(
            text=f"{total} ID(s) • {lotes} lote(s) de até {TAM_LOTE} • ordem crescente")

    # ---------- dados ----------

    def salvar_dados(self):
        try:
            pausa = float(self.campo_pausa.get().replace(",", "."))
        except (ValueError, AttributeError):
            pausa = 5.0
        gravar_json(ARQ_DADOS, {
            "ids": self.ids,
            "comentario": self.campo_comentario.get(),
            "pausa": pausa,
        })

    # ---------- aba Coordenadas ----------

    def montar_aba_coord(self, pai):
        card = cartao(pai)
        card.pack(fill="both", expand=True)

        rotulo(card, "Coordenadas dos cliques", ("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=6, sticky="w")
        rotulo(
            card,
            f"Capturar: a janela some e você tem {SEGUNDOS_CAPTURA} s para pôr o "
            "mouse no local (um bipe avisa). Ver: mostra onde o ponto está.",
            ("Segoe UI", 9), SUB,
        ).grid(row=1, column=0, columnspan=6, sticky="w", pady=(2, 10))

        self.coord_campos = {}
        self.coord_status = {}
        for n, (chave, nome, padrao) in enumerate(PASSOS):
            r = 2 + n
            rotulo(card, nome, FONTE_B, width=32, anchor="w").grid(
                row=r, column=0, sticky="w", pady=3)

            salvo = self.coord_salvas.get(chave)
            valor = salvo if salvo else (list(padrao) if padrao else None)

            ex, ey = campo(card, 7), campo(card, 7)
            if valor:
                ex.insert(0, str(valor[0]))
                ey.insert(0, str(valor[1]))
            ex.grid(row=r, column=1, padx=3, ipady=3)
            ey.grid(row=r, column=2, padx=3, ipady=3)
            for e in (ex, ey):
                e.bind("<KeyRelease>", lambda ev, k=chave: self.atualizar_status(k))

            botao(card, "Capturar", lambda k=chave: self.capturar(k), AZUL).grid(
                row=r, column=3, padx=(8, 3))
            botao(card, "Ver", lambda k=chave: self.ver(k), "#3f3f4a").grid(
                row=r, column=4, padx=3)

            st = rotulo(card, "", ("Segoe UI", 9, "bold"), width=9, anchor="w")
            st.grid(row=r, column=5, padx=(8, 0))

            self.coord_campos[chave] = (ex, ey)
            self.coord_status[chave] = st
            self.atualizar_status(chave)

        botao(card, "Salvar coordenadas", self.salvar_coordenadas, VERDE).grid(
            row=2 + len(PASSOS), column=0, columnspan=6, sticky="w", pady=(16, 0))

    def ler_coord(self, chave):
        """Retorna (x, y) ou None se vazio. Levanta ValueError se inválido."""
        ex, ey = self.coord_campos[chave]
        tx, ty = ex.get().strip(), ey.get().strip()
        if not tx and not ty:
            return None
        return int(tx), int(ty)

    def atualizar_status(self, chave):
        st = self.coord_status[chave]
        try:
            pos = self.ler_coord(chave)
        except ValueError:
            st.configure(text="inválido", fg=VERMELHO)
            return
        if pos is None:
            st.configure(text="pendente", fg=LARANJA)
        else:
            st.configure(text="✔ ok", fg=VERDE)

    def salvar_coordenadas(self, silencioso=False):
        dados = {}
        for chave, nome, _ in PASSOS:
            try:
                pos = self.ler_coord(chave)
            except ValueError:
                messagebox.showerror("Erro", f"Coordenada inválida em:\n{nome}")
                return False
            dados[chave] = list(pos) if pos else None
        gravar_json(ARQ_COORD, dados)
        self.coord_salvas = dados
        if not silencioso:
            messagebox.showinfo("Sucesso", "Coordenadas salvas com sucesso!")
        return True

    def capturar(self, chave):
        messagebox.showinfo(
            "Captura",
            "Depois do OK a janela vai sumir.\n\n"
            "Posicione o mouse no local desejado.\n"
            f"Você terá {SEGUNDOS_CAPTURA} segundos (um bipe marca a captura).",
        )
        self.janela.withdraw()
        self.janela.after(
            SEGUNDOS_CAPTURA * 1000, lambda: self.finalizar_captura(chave))

    def finalizar_captura(self, chave):
        x, y = pa.position()
        if winsound:
            winsound.Beep(1000, 250)
        self.janela.deiconify()
        ex, ey = self.coord_campos[chave]
        ex.delete(0, tk.END)
        ey.delete(0, tk.END)
        ex.insert(0, str(x))
        ey.insert(0, str(y))
        self.atualizar_status(chave)
        self.salvar_coordenadas(silencioso=True)
        messagebox.showinfo("Capturado", f"X: {x}\nY: {y}")

    def ver(self, chave):
        try:
            pos = self.ler_coord(chave)
        except ValueError:
            messagebox.showerror("Erro", "Coordenada inválida.")
            return
        if pos is None:
            messagebox.showwarning("Pendente", "Capture esta coordenada primeiro.")
            return
        self.janela.withdraw()
        pa.moveTo(pos[0], pos[1], duration=0.4)
        self.janela.after(3000, self.janela.deiconify)

    def coords_validas(self):
        """Dicionário chave -> (x, y), ou None (e avisa) se faltar algo."""
        largura, altura = pa.size()
        coords, faltando, fora = {}, [], []
        for chave, nome, _ in PASSOS:
            try:
                pos = self.ler_coord(chave)
            except ValueError:
                faltando.append(nome)
                continue
            if pos is None:
                faltando.append(nome)
            else:
                if not (0 <= pos[0] < largura and 0 <= pos[1] < altura):
                    fora.append(nome)
                coords[chave] = pos
        if faltando or fora:
            texto = ""
            if faltando:
                texto += "Faltando/inválido:\n- " + "\n- ".join(faltando)
            if fora:
                texto += "\n\nFora da tela:\n- " + "\n- ".join(fora)
            messagebox.showerror("Coordenadas", texto.strip())
            return None
        return coords

    # ---------- aba Executar ----------

    def montar_aba_exec(self, pai, pausa):
        card = cartao(pai)
        card.pack(fill="both", expand=True)
        card.columnconfigure(0, weight=1)

        rotulo(card, "Executar automação", ("Segoe UI", 14, "bold")).grid(
            row=0, column=0, sticky="w")
        self.lbl_resumo = rotulo(card, "", FONTE, SUB)
        self.lbl_resumo.grid(row=1, column=0, sticky="w", pady=(2, 10))

        rotulo(card, "Checklist antes de iniciar", FONTE_B).grid(
            row=2, column=0, sticky="w")
        self.checks = []
        for i, texto in enumerate(CHECKLIST):
            var = tk.BooleanVar(value=False)
            tk.Checkbutton(
                card, text=texto, variable=var, bg=CARD, fg=TXT,
                selectcolor=CAMPO, activebackground=CARD, activeforeground=TXT,
                font=FONTE, anchor="w",
            ).grid(row=3 + i, column=0, sticky="w", pady=1)
            self.checks.append(var)

        opcoes = tk.Frame(card, bg=CARD)
        opcoes.grid(row=8, column=0, sticky="w", pady=(14, 0))
        rotulo(opcoes, "Pausa entre ações (s)", FONTE_B).grid(row=0, column=0, sticky="w")
        self.campo_pausa = campo(opcoes, 6)
        self.campo_pausa.insert(0, str(pausa))
        self.campo_pausa.grid(row=0, column=1, padx=8, ipady=3)
        self.campo_pausa.bind("<FocusOut>", lambda e: self.salvar_dados())

        rotulo(opcoes, "Iniciar a partir do ID", FONTE_B).grid(
            row=1, column=0, sticky="w", pady=(8, 0))
        self.campo_inicio = campo(opcoes, 10)
        self.campo_inicio.grid(row=1, column=1, padx=8, pady=(8, 0), ipady=3)
        rotulo(opcoes, "(vazio = do primeiro)", ("Segoe UI", 9), SUB).grid(
            row=1, column=2, sticky="w", pady=(8, 0))

        botao(card, "▶  Iniciar automação", self.iniciar, VERDE).grid(
            row=9, column=0, sticky="w", pady=(16, 8))

        rotulo(card, "Registro da execução", FONTE_B).grid(
            row=10, column=0, sticky="w")
        self.txt_log = tk.Text(
            card, height=9, bg=CAMPO, fg=TXT, font=("Consolas", 9),
            relief="flat", highlightthickness=1, highlightbackground=BORDA,
            state="disabled",
        )
        self.txt_log.grid(row=11, column=0, sticky="nsew", pady=(4, 0))
        card.rowconfigure(11, weight=1)

    def atualizar_resumo(self):
        total = len(self.ids)
        coment = self.campo_comentario.get()
        self.lbl_resumo.configure(
            text=f"{total} ID(s) na lista • comentário: “{coment}”")

    def log(self, msg):
        linha = f"[{datetime.now():%d/%m/%Y %H:%M:%S}] {msg}"
        self.txt_log.configure(state="normal")
        self.txt_log.insert(tk.END, linha + "\n")
        self.txt_log.see(tk.END)
        self.txt_log.configure(state="disabled")
        with open(ARQ_LOG, "a", encoding="utf-8") as f:
            f.write(linha + "\n")

    # ---------- automação ----------

    def processar_id(self, id_atual, comentario, c):
        """Um ciclo completo para um ID, só com cliques por coordenadas."""

        def clicar(chave):
            pa.click(*c[chave])

        # 1) Localizar o cadastro pelo ID
        clicar("campo_localizar_id")
        pa.write(id_atual)
        pa.press("enter")
        pa.press("enter")

        # 2) Abrir a área de anexos
        clicar("btn_anexo")

        # 3) Comentário comum
        clicar("campo_comentario")
        pyperclip.copy(comentario)
        pa.hotkey("ctrl", "v")

        # 4) Selecionar e anexar o documento
        clicar("btn_selecionar_doc")
        clicar("arquivo_na_janela")
        pa.press("enter")

        # 5) Salvar o anexo (rola a página até o fim antes de clicar)
        clicar("area_neutra")
        pa.scroll(-2000)
        time.sleep(2)
        clicar("btn_salvar")

        # 6) Apagar o documento da pasta
        clicar("barra_pasta")
        clicar("arquivo_excluir")
        pa.press("delete")

        # 7) Voltar ao navegador: Cadastros > Localizar Cadastros
        clicar("barra_navegador")
        clicar("menu_cadastros")
        clicar("btn_voltar_localizar")

    def iniciar(self):
        self.salvar_dados()

        if not all(v.get() for v in self.checks):
            messagebox.showwarning("Checklist", "Marque todos os itens do checklist.")
            return
        if not self.ids:
            messagebox.showwarning("Sem IDs", "Cadastre ao menos um ID na aba IDs.")
            return
        if not self.salvar_coordenadas(silencioso=True):
            return
        coords = self.coords_validas()
        if coords is None:
            return

        try:
            pausa = float(self.campo_pausa.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Erro", "Pausa inválida.")
            return

        inicio = self.campo_inicio.get().strip()
        if inicio and inicio not in self.ids:
            messagebox.showerror("Erro", f"O ID {inicio} não está na lista.")
            return
        fila = self.ids[self.ids.index(inicio):] if inicio else list(self.ids)
        comentario = self.campo_comentario.get()

        if not messagebox.askokcancel(
            "Confirmar",
            f"Processar {len(fila)} ID(s) com o comentário:\n“{comentario}”\n\n"
            f"A janela some e começa em 5 s.\n"
            "Para parar: mouse no canto superior esquerdo da tela.",
        ):
            return

        pa.PAUSE = pausa
        pa.FAILSAFE = True

        self.janela.withdraw()
        self.log(f"Início: {len(fila)} ID(s), pausa {pausa}s")
        time.sleep(5)

        feitos, atual, erro = 0, None, None
        try:
            for atual in fila:
                self.processar_id(atual, comentario, coords)
                feitos += 1
                self.log(f"OK  {atual}")
        except pa.FailSafeException:
            erro = "Interrompido pelo canto da tela."
        except Exception as ex:  # noqa: BLE001
            erro = f"Erro: {ex}"

        for v in self.checks:
            v.set(False)
        self.janela.deiconify()

        if erro:
            self.log(f"{erro} ID em andamento: {atual} (reinicie por ele)")
            self.campo_inicio.delete(0, tk.END)
            self.campo_inicio.insert(0, atual)
            messagebox.showwarning(
                "Parou antes do fim",
                f"{erro}\n\nConcluídos: {feitos} de {len(fila)}.\n"
                f"Reinicie a partir do ID {atual}.",
            )
        else:
            self.log(f"Fim: {feitos} ID(s) concluído(s).")
            self.campo_inicio.delete(0, tk.END)
            messagebox.showinfo("Concluído", f"{feitos} ID(s) processado(s).")

    # ---------- encerramento ----------

    def fechar(self):
        self.salvar_dados()
        self.salvar_coordenadas(silencioso=True)
        self.janela.destroy()

    def rodar(self):
        self.janela.mainloop()


if __name__ == "__main__":
    App().rodar()