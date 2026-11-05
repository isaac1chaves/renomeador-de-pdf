# Histórico de alterações

## 2.1.0
- Mantém o acesso ao Tkinter na thread principal e recebe resultados do OCR e atualizações de progresso por meio de uma fila segura para uso entre threads.
- Reconhece erros comuns de leitura do cabeçalho Chapa/Nome pelo OCR, incluindo "Chupa/Nomo" e "Chiupa/Nomo".
- Registra o formato de saída selecionado antes de iniciar a análise em segundo plano.
- Permite deixar campos de correção manual em branco, oferece uma lista de meses em letras maiúsculas e posiciona as janelas de diálogo na área de trabalho virtual do Windows.
- Adiciona à barra de ferramentas a reanálise dos arquivos selecionados, além de propriedades do arquivo e ações organizadas no menu de contexto.

## 2.0.4
- Deixa de usar nomes de arquivos originais como evidência para o OCR ou para identificar a matrícula.
- Calcula a confiança somente com base na linha do cabeçalho Chapa/Nome.
- Usa o mesmo percentual arredondado na exibição e na decisão entre OK e REVISAR.
- Interrompe a captura do nome ao encontrar variações de OCR de rótulos como admissão, função, horário, lotação e contrato.

## 2.0.3
- Corrige a perspectiva e remove margens escuras de folhas fotografadas quando identifica um contorno confiável da página.
- Usa o nome original do arquivo na interpretação do OCR, permitindo que um nome de arquivo numérico confirme a matrícula em vez do nome de um PDF temporário.
- Mantém os caminhos de OCR otimizado e abrangente introduzidos na versão 2.0.2.

## 2.0.2
- Restaura a rotina abrangente de OCR, já testada, como alternativa de compatibilidade somente para arquivos que os caminhos otimizados não conseguem reconhecer.
- Mantém o processamento rápido para folhas de ponto comuns e documentos nítidos, sem deixar de recuperar digitalizações difíceis reconhecidas pela versão 2.0.0.

## 2.0.1
- Prioriza o caminho rápido de reconhecimento de folhas de ponto antes do OCR mais custoso da página inteira.
- Reduz o OCR de documentos de até doze tentativas de orientação e layout por página para duas tentativas principais e, raramente, uma alternativa com a página girada.
- Reduz a renderização da página inteira de 2,4x para 1,8x e interrompe o processamento assim que há evidências suficientes para a classificação.

## 2.0.0
- Versão final do código-fonte institucional após o protótipo validado.
- Mantém os limites operacionais de 300 arquivos, 1.000 páginas, 100 MB por arquivo, aviso para arquivos acima de 30 MB e quatro tarefas paralelas.
- Preserva o lote atual ao adicionar mais arquivos ou selecionar outra pasta.
- Limpa o lote exibido junto com os dados locais da sessão para evitar referências desatualizadas.
- Padroniza os textos finais da interface em português e remove estilos não utilizados.

## 1.8.5
- Centraliza cada janela modal personalizada sobre a janela principal e mantém-na dentro da área visível da tela.

## 1.8.4
- Padroniza as mensagens restantes da interface em português.
- Substitui os textos de exportação que mencionavam somente PDF por mensagens compatíveis com outros formatos.
- Corrige o histórico de versões e os metadados do repositório.

## 1.8.3
- Usa o nome original do arquivo para nomear automaticamente ou manualmente atestados e declarações.
- Padroniza os títulos das etapas, os contadores e a acentuação em português na interface.

## 1.8.2
- Diferencia arquivos com o mesmo nome original quando estão em pastas distintas.
- Exibe N/D para atestados e declarações classificados, em vez de apresentar um percentual de confiança artificial.
- Abre a pasta de origem do arquivo e informa os nomes originais em caso de erro na exportação.

## 1.8.1
- Mantém os atestados e as declarações prontos quando as opções de nomenclatura são alteradas.
- Desvincula as opções de nomenclatura da confiança do OCR.
- Permite analisar arquivos sem selecionar campos para compor o nome.

## 1.8.0
- Aceita imagens válidas e decodificáveis mesmo quando a extensão do arquivo não corresponde ao formato identificado.
- Usa o nome original do arquivo, sem extensão, quando todos os campos de nomenclatura estão desativados.

## 1.7.9
- Valida as assinaturas reais dos arquivos e rejeita arquivos renomeados ou corrompidos, inclusive arquivos MP4 com extensão PDF.

## 1.7.8
- Preserva o nome e a extensão originais na coluna Arquivo original.
- Faz com que a extensão em Novo nome corresponda ao formato de exportação selecionado.

## 1.7.7 — versão-base institucional
- Remove o atualizador automático e a dependência de um repositório pessoal.
- Preserva a indicação de progresso do OCR.
- Adiciona as pastas `TERMS` e `DOCUMENTATION`.
- Substitui o script de publicação no GitHub por `BUILD_RDF_PACKAGE.bat`.
