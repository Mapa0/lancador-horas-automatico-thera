# Lançador de Horas Automático Thera

Programa Python com interface gráfica para preencher o **Timesheet Multidados da Thera** a partir de um roteiro mensal em JSON.

Você escolhe o arquivo do mês, informa usuário e senha, seleciona Chrome ou Microsoft Edge e confere as narrativas. O programa entra no sistema, escolhe o mês, seleciona o dia 1 no calendário lateral, abre a visualização mensal e preenche os dias elegíveis.

**Horário aplicado: 08:00 → 12:00 → 13:00 → 17:00, total de 8 horas por dia.**

Não é necessário editar o Python nem passar parâmetros na linha de comando. O roteiro muda a cada mês; o programa continua o mesmo.

## Começar no Windows

1. Instale [Python 3.10 ou superior](https://www.python.org/downloads/windows/) com Tcl/Tk. No instalador tradicional, marque **Add Python to PATH**.
2. Tenha **Google Chrome ou Microsoft Edge** instalado.
3. [Baixe o ZIP do repositório](https://github.com/Mapa0/lancador-horas-automatico-thera/archive/refs/heads/main.zip) e **extraia** a pasta. Não execute de dentro do ZIP.
4. Gere seu arquivo do mês usando [o prompt para o agente de IA](PROMPT_PARA_IA.md). Informe seus próprios projeto, cliente, localidade e atividades.
5. Dê dois cliques em **iniciar.bat**.
6. Na primeira execução, aceite a instalação do Playwright se ainda não estiver disponível. Precisa de internet para essa instalação.
7. Escolha o arquivo JSON do mês. Informe login e senha do Multidados e selecione o navegador instalado.
8. Deixe **Salvar os lançamentos automaticamente** desmarcado na primeira tentativa.
9. Clique em **Iniciar**. Revise o primeiro formulário preenchido. Essa prévia termina sem clicar em Salvar.
10. Para gravar, abra novamente, escolha o mesmo JSON, marque a opção de salvamento, revise a lista e confirme o lote.

O arquivo em exemplos/ é fictício e contém somente_exemplo: true. O programa recusa iniciar o navegador com ele. Crie seu roteiro real e use somente_exemplo: false.

### Instalação manual opcional

No terminal, dentro da pasta extraída:

~~~powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe thera_horas.py
~~~

A interface abre sem argumentos adicionais. Nesse modo, execute novamente pelo Python da .venv para continuar usando o mesmo ambiente.

O atalho iniciar.bat usa o Python padrão do computador e oferece instalar a dependência nesse Python. Não é um executável independente: ter Python e um dos navegadores instalados é obrigatório.

## Como gerar as entradas com IA

Abra [PROMPT_PARA_IA.md](PROMPT_PARA_IA.md), copie o prompt e envie ao agente que conhece suas atividades. Ele orienta o agente a:

- pedir mês, município/UF, projeto, cliente e atividades;
- verificar feriados em fontes oficiais e excluir finais de semana;
- criar narrativas curtas com base no trabalho confirmado;
- separar atividades realizadas de projeções;
- entregar o JSON exatamente no formato aceito.

Revise o arquivo antes de usar. A automação aplica sempre 8 horas: dias com jornada diferente devem ser tratados manualmente. Atividades sugeridas ou futuras devem permanecer como projeções.

## Formato do JSON

Veja [exemplos/lancamentos.exemplo.json](exemplos/lancamentos.exemplo.json) e [o contrato JSON Schema](schemas/lancamentos.schema.json).

| Campo | Conteúdo |
|---|---|
| referencia | Um único mês no formato AAAA-MM. |
| localidade | Objeto com pais, uf e municipio, usados para documentar o calendário aplicável. |
| codigo_projeto | Código exato como texto; preserve os zeros à esquerda. |
| nome_projeto | Nome completo exatamente como aparece no seletor do sistema. |
| nome_cliente | Nome do cliente exatamente como aparece no sistema. |
| usuario | Opcional; pode ficar vazio e ser informado na janela. Nunca inclua a senha. |
| somente_exemplo | true impede iniciar lançamentos; use false no seu roteiro real. |
| feriados | Lista de datas AAAA-MM-DD sem expediente, mesmo que vazia. |
| fontes_feriados | Lista não vazia de URLs usadas para verificar o calendário. |
| lancamentos | Lista de objetos com data, narrativa e projecao. |

Para cada lançamento:

- **data:** AAAA-MM-DD, dentro do mês de referência e sem repetição.
- **narrativa:** texto curto e não vazio com o trabalho realizado ou planejado.
- **projecao:** false para trabalho e jornada confirmados; true para planejamento ainda não confirmado.

Não inclua outros campos. O programa rejeita campos desconhecidos, incluindo campos de senha, bem como datas inválidas, repetições ou registros fora do mês.

### Feriados, finais de semana e datas futuras

Finais de semana são calculados pelo programa. Os feriados vêm da lista **feriados do JSON**: o programa não consulta calendário on-line nem descobre feriados municipais sozinho.

O agente deve conferir os feriados do ano para o município e a UF corretos. Pontos facultativos e emendas só devem ser excluídos se a empresa realmente os adotar. No exemplo de outubro de 2026 para São Paulo, 12/10 aparece no [calendário oficial da Prefeitura](https://www2.prefeitura.sp.gov.br/web/gestao/w/calendario_2026).

Datas futuras são bloqueadas com base no relógio do computador. Uma linha com projecao: true continua bloqueada mesmo depois que sua data passou. Só altere para false depois de confirmar que o trabalho aconteceu.

## Fluxo do programa

1. Valida o JSON e calcula os dias elegíveis.
2. Mostra as narrativas e os dias que serão ignorados.
3. Abre uma janela temporária do navegador selecionado.
4. Faz login com as informações digitadas.
5. Navega até o mês informado e seleciona o dia 1.
6. Abre o calendário mensal e espera até **3 minutos por etapa de carregamento** pelo servidor e pelas datas necessárias.
7. Lê os dias que já têm lançamento e os ignora.
8. Abre o formulário do dia, seleciona o projeto pelo nome e código, aplica os quatro horários e a narrativa.
9. Confirma os campos e o total de 08:00.
10. Em prévia, mostra o primeiro dia pendente sem gravar. Em salvamento, pede a confirmação do lote e confere cada registro no calendário após salvar.

Classe, fase, atividade e demais padrões preenchidos pelo projeto são preservados. O programa não modifica lançamentos existentes nem tenta completar dias parcialmente preenchidos.

## Salvamento e interrupções

A opção de salvamento começa desmarcada. Mesmo quando marcada, há uma confirmação final das datas, do projeto e do total de horas antes do lote.

Cada registro recebe **um único clique em Salvar**. Se o resultado for incerto, a execução para; ela não repete o clique automaticamente.

Se o servidor estiver lento, deixe o navegador terminar de carregar. Se a espera se esgotar, confira a mensagem e o calendário antes de executar novamente. Os dias já preenchidos serão ignorados na próxima execução.

Durante a automação, aguarde antes de interagir com a janela do navegador para não mudar o mês ou o formulário enquanto o programa trabalha.

## Privacidade e arquivos locais

A senha fica apenas em memória durante a execução. Não é escrita no JSON, não é guardada no cofre do Windows e não é incluída no registro de execução. O navegador usa um contexto temporário, sem aproveitar seu perfil pessoal.

A pasta evidencias/ recebe capturas de tela e um registro com datas e status. As capturas podem mostrar nomes, projetos e narrativas; trate esses arquivos como dados do seu trabalho.

O .gitignore exclui roteiros JSON reais, evidências, logs, ambiente virtual e arquivos de configuração locais. Apenas exemplos fictícios e o schema são versionados. Não envie arquivos de trabalho ou credenciais em issues públicas.

## Problemas comuns

| Situação | O que fazer |
|---|---|
| Python não encontrado | Instale Python 3.10+ e confira py --version ou python --version. |
| A janela não abre / falta tkinter | Instale a distribuição oficial do Python com Tcl/Tk. |
| Playwright não instala | Confirme conexão ao PyPI e o Python usado; instale com python -m pip install -r requirements.txt. |
| Chrome ou Edge não abre | Selecione o navegador instalado. Não é necessário instalar os dois. |
| JSON não abre | Use UTF-8, datas ISO, aspas duplas e JSON sem comentários. |
| “Arquivo de exemplo” | Gere seu arquivo com seus dados e somente_exemplo: false. |
| Não há dias elegíveis | Confira datas futuras, projeções, feriados e dias da semana. |
| Todos os dias já preenchidos | O programa ignora esses dias; revise diretamente no sistema se precisar corrigir algo. |
| Projeto não encontrado | Copie código, nome completo e cliente exatamente do seletor do Multidados. |
| Calendário não ficou pronto | Aguarde o servidor normalizar e tente novamente; a mensagem identifica a etapa. |
| Login não confirmado | Confira usuário/senha e eventual verificação manual exigida pelo site. |
| Parou depois de Salvar | Confira se o último registro apareceu no calendário antes de repetir. |

## Limites conhecidos

- Adaptado à interface do domínio thera.multidadosti.com.br.
- Uma execução trata um único mês e um projeto/cliente.
- Horários fixos; não oferece horas extras, jornadas parciais ou vários lançamentos no mesmo dia.
- Mudanças no HTML ou nos nomes dos controles do site podem exigir atualização dos seletores.
- CAPTCHA/MFA, quando exigidos, não são automatizados.
- A confirmação de um salvamento usa o registro exibido pelo calendário; não há consulta independente ao banco interno do Multidados.
- Os testes são feitos com página sintética e respostas interceptadas, sem gravar horas reais. Isso não garante disponibilidade do servidor em cada execução.

## Testes e desenvolvimento

Testes de validação, calendário e tratamento de erros, sem abrir o site real:

~~~powershell
python -m unittest discover -s tests -v
~~~

Para incluir os testes de navegador usando Chrome instalado, no PowerShell:

~~~powershell
$env:THERA_RUN_BROWSER_TESTS = "1"
$env:THERA_TEST_BROWSER = "chrome"
python -m unittest discover -s tests -v
~~~

Para usar o Chromium de testes em vez de um navegador instalado:

~~~powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
$env:THERA_RUN_BROWSER_TESTS = "1"
Remove-Item Env:THERA_TEST_BROWSER -ErrorAction SilentlyContinue
python -m unittest discover -s tests -v
~~~

Os testes foram executados localmente em Windows com Chrome e Microsoft Edge. As requisições são interceptadas com HTML fictício; não há login real. O repositório não inclui uma esteira de testes automática.

## Estrutura

~~~text
thera_horas.py                    Programa com interface gráfica
iniciar.bat                      Atalho de execução no Windows
requirements.txt                 Dependência do navegador
PROMPT_PARA_IA.md                 Prompt para gerar o roteiro de cada mês
exemplos/lancamentos.exemplo.json Roteiro fictício bloqueado para lançamentos
schemas/lancamentos.schema.json  Contrato do JSON
tests/                          Testes com dados e página fictícios
~~~

## Licença

[MIT](LICENSE). Projeto independente, sem vínculo oficial com a Thera ou com o fornecedor Multidados.

