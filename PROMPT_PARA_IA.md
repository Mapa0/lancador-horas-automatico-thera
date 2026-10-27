# Prompt para gerar o roteiro mensal

Copie o texto abaixo para o agente de IA que acompanha suas atividades. Preencha os dados do início e descreva ou anexe as atividades reais do mês. O agente deve entregar um JSON UTF-8, sem credenciais.

---

Você vai preparar um roteiro para o **Lançador de Horas Automático Thera**.

## Meus dados de entrada

- Mês de referência: AAAA-MM
- Data de hoje: AAAA-MM-DD
- País, UF e município onde o calendário de trabalho se aplica:
- Código do projeto, exatamente como aparece no Multidados, como texto, preservando zeros:
- Nome completo do projeto, exatamente como aparece no Multidados:
- Nome do cliente, exatamente como aparece no Multidados:
- Atividades reais realizadas e datas ou período confirmado:
- Dias com férias, folga, ausência ou jornada diferente de 8 horas:
- Dias futuros para os quais desejo somente planejar atividades, se houver:
- Pontos facultativos e emendas que minha empresa de fato adotou, se houver:

Se faltar código/nome do projeto, cliente, localidade, mês ou confirmação das atividades, pergunte antes de finalizar. Nunca peça minha senha.

## Regras de calendário e conteúdo

1. Considere somente o mês e o ano informados. Calcule os dias da semana corretamente.
2. Exclua sábados, domingos e feriados aplicáveis: nacionais, estaduais e municipais. Verifique o calendário do ano em fontes oficiais do governo/estado/prefeitura e inclua as URLs consultadas em fontes_feriados.
3. Não considere automaticamente Carnaval, Corpus Christi, emendas ou outros pontos facultativos como folga da empresa. Confirme o calendário adotado antes de excluí-los. Datas adicionais confirmadas como sem expediente podem ser colocadas em feriados.
4. A automação não consulta feriados on-line. A lista feriados do JSON precisa estar correta e completa para a localidade informada.
5. Não inclua férias, folgas ou ausências. Não inclua como realizado um dia com jornada diferente de 8 horas: este lançador usa sempre 08:00–12:00 e 13:00–17:00.
6. Escreva uma narrativa curta, concreta e em português para cada dia. Use apenas informações fornecidas ou confirmadas por mim; não invente entregas, aprovações, testes, reuniões nem trabalho realizado para completar o mês.
7. Use projecao: false somente para datas passadas ou de hoje com atividades e jornada de 8 horas confirmadas. Se a distribuição das atividades entre os dias for apenas uma sugestão ainda não validada, use projecao: true.
8. Todo dia futuro ou atividade apenas planejada deve ter projecao: true. O programa ignora essas linhas. Mesmo após a data passar, a projeção continuará ignorada até eu confirmar e mudar o campo para false.
9. Gere no máximo uma entrada por dia, em ordem crescente. Não coloque lançamentos em outro mês. Não adicione horários: o programa aplica os quatro horários fixos.
10. Não inclua senha, token, CPF, informações pessoais desnecessárias ou outros segredos. O login é solicitado localmente pelo programa. usuario pode ficar vazio.
11. Se não tiver acesso às fontes oficiais dos feriados, não alegue que verificou. Peça o calendário oficial ou a confirmação das datas antes de entregar o roteiro final.
12. O programa ignora dias já preenchidos no Multidados e não complementa jornadas parciais.

## Formato exato

Use somente estes campos. Troque todos os exemplos pelos meus dados. Datas: AAAA-MM-DD. Booleanos: true ou false, sem aspas. codigo_projeto deve continuar sendo uma string.

~~~json
{
  "referencia": "2026-10",
  "localidade": {"pais": "BR", "uf": "SP", "municipio": "São Paulo"},
  "codigo_projeto": "CODIGO_EXATO_DO_MEU_PROJETO",
  "nome_projeto": "NOME_EXATO_DO_MEU_PROJETO",
  "nome_cliente": "NOME_EXATO_DO_MEU_CLIENTE",
  "usuario": "",
  "somente_exemplo": false,
  "feriados": ["2026-10-12"],
  "fontes_feriados": ["URL_OFICIAL_REAL_CONSULTADA"],
  "lancamentos": [
    {
      "data": "2026-10-01",
      "narrativa": "Descrição curta e confirmada do trabalho realizado neste dia.",
      "projecao": false
    }
  ]
}
~~~

O exemplo acima não é um calendário completo nem deve ser reutilizado sem adaptar mês, localidade e feriados. O contrato completo está em schemas/lancamentos.schema.json. O programa também valida datas repetidas, datas fora do mês, tipos dos campos e elegibilidade.

## Antes de entregar

- Confira que todas as datas pertencem ao mês solicitado, sem repetições.
- Recalcule os dias da semana e aplique os feriados verificados.
- Confirme que não atribuiu trabalho realizado a datas futuras ou não confirmadas.
- Informe, fora do arquivo, quantos dias são realizados, quantos são projeções e o total de horas dos dias realizados (dias × 8).
- Entregue o arquivo lancamentos-AAAA-MM.json em UTF-8, sem comentários nem cercas Markdown dentro do arquivo.
- Se não houver nenhum dia confirmado nem projeção solicitada, diga isso em vez de inventar uma lista.

