# Distribuidora Varejo

Sistema desktop completo para operação varejista de uma distribuidora de
bebidas. Contempla autenticação, cadastros, estoque, compras, PDV, caixa,
pedidos e entregas, financeiro, relatórios, auditoria, configurações e backup.

## Identidade visual

A marca **Adega do Bruninho** está incorporada em
`resources/images/adega_do_bruninho_logo.png` e é usada no login, menu lateral e
ícone da aplicação. Os temas claro e escuro seguem a paleta da marca: preto e
grafite como base, dourado e laranja como destaques e branco para contraste.
Gráficos e estados de foco seguem a mesma identidade.

## Janela principal e painel

- Menu lateral recolhível com páginas liberadas pelo RBAC.
- Barra superior com nome, perfil, troca de tema e encerramento da sessão.
- Temas claro e escuro persistidos nas preferências locais do computador.
- Dezesseis cards operacionais e financeiros.
- Gráficos de vendas por dia, mês, categoria, produto, forma de pagamento,
  embalagem e comparação entre receita, custo e lucro.
- Filtros por período, usuário, produto, categoria, pagamento e tipo de venda.
- Valores em real brasileiro e datas no formato `dd/MM/yyyy`.
- Consultas agregadas executadas em `QThreadPool`, sem bloquear a interface.
- Dashboard protegido por permissão tanto na navegação quanto no serviço.
- Estado vazio suportado enquanto os módulos de vendas ainda não foram criados.

## Clientes

- Nome, CPF e celular são opcionais; o cadastro também permite selecionar o
  status Ativo/Inativo diretamente no formulário.
- Nascimento, WhatsApp, e-mail, observações e confirmação de maioridade também
  são opcionais.
- Endereço principal opcional e até dez endereços adicionais estruturados.
- Máscaras de CPF, telefone e CEP; validação algorítmica de CPF.
- Pesquisa por nome, CPF ou telefone, filtro de status e paginação configurável.
- Edição, ativação e inativação lógica, protegidas por RBAC e auditoria.
- CPF único quando informado; vários clientes podem permanecer sem CPF.
- Total gasto, ticket médio, última compra e histórico, preparados para a futura
  coleção de vendas.
- Data de nascimento persistida como meia-noite UTC e exibida como `dd/MM/yyyy`.
- A confirmação de maioridade é recusada pelo serviço quando a data indica menos
  de 18 anos.

## Fornecedores

- Cadastro de razão social, nome fantasia, CPF/CNPJ, inscrição estadual,
  telefones, e-mail, endereço e contato comercial.
- Prazo de entrega, condição de pagamento, observações e status.
- Validação algorítmica e normalização de CPF/CNPJ, com documento único.
- Pesquisa por razão social, nome fantasia ou documento, filtro de status e
  paginação.
- Edição e inativação lógica protegidas por RBAC e auditoria.
- Histórico com nota, data e total das compras, além do último custo conhecido
  de cada produto.
- As abas de navegação usam somente texto; indicadores visuais permanecem nos
  controles de tema, sair e recolher.

## Categorias e produtos

- Carga idempotente das quinze categorias iniciais previstas no escopo.
- Manutenção de categorias com nome único, descrição e status.
- Cadastro de produto com códigos, descrição, categoria, marca, volume,
  embalagem, fornecedor, localização, lote, validade, foto e status.
- Custos, preços e promoções persistidos como `Decimal128`; cálculos usam
  exclusivamente `Decimal`.
- Preços independentes para unidade e fardo, com composição obrigatória quando
  houver dados de fardo.
- Estoque armazenado em unidades e apresentado também como fardos + unidades.
- Código interno único e códigos de barras globalmente únicos entre unidade e
  fardo, inclusive quando utilizados em campos diferentes.
- Pesquisa por nome, código, barras ou marca, além de filtros por categoria,
  status e estoque baixo.
- Alterações de preço e composição do fardo possuem eventos específicos na
  auditoria.
- Margem de lucro fica oculta para perfis sem `lucro.visualizar`.
- O estoque inicial pode ser informado no cadastro; alterações posteriores de
  saldo ficam reservadas ao módulo de estoque da Etapa 8.
- A tabela de produtos exibe o fornecedor principal e oferece um botão de
  informações completas. Custos e margem continuam condicionados às permissões.
- As abas internas Produtos/Categorias têm contraste reforçado em ambos os temas,
  inclusive nos estados selecionado e hover.
- O formulário de produto foi simplificado para uma única tela com nome, código
  de barras, categoria, estoque mínimo, tipo, preços de compra/venda e
  fornecedor. O código interno é gerado automaticamente e permanece invisível.
- A tabela não exibe marca e apresenta `Estoque mínimo` no lugar do saldo atual.

## Venda por unidade e por fardo

- Configuração de fardo em diálogo separado do cadastro simplificado.
- Quantidade de unidades, código de barras e preços normal/promocional do fardo.
- Preços de unidade e fardo independentes, sempre calculados com `Decimal`.
- Leitura de código identifica automaticamente unidade ou fardo.
- Conversão de fardos para unidades e devolução na mesma base.
- Validação de saldo individual e acumulado em carrinhos que misturam unidade e
  fardo do mesmo produto.
- Produtos sem composição de fardo são recusados nessa modalidade.
- Alterações de composição e preços do fardo são auditadas separadamente.
- A configuração é atômica e a unicidade do código de barras é garantida pelo
  MongoDB inclusive entre códigos de unidade e de fardo.

## Estoque, lotes, validade e inventário

- Saldo central mantido exclusivamente em unidades, com exibição convertida em
  fardos e unidades.
- Entradas, devoluções, trocas, perdas, avarias, vencimentos, uso interno,
  bonificações, ajustes manuais e inventários.
- Quantidade informada por unidade/fardo e quantidade convertida registradas no
  histórico junto dos saldos anterior e final.
- Baixas usam atualização condicional atômica no MongoDB, impedindo concorrência
  de gerar saldo negativo.
- Estoque negativo requer autorização explícita e perfil Administrador.
- Controle de lotes com saldo em unidades, validade e alerta configurável.
- Todos os lotes com saldo são exibidos como vencidos, próximos do vencimento,
  dentro da validade ou sem validade.
- Inventário define o saldo contado e registra a diferença na auditoria.
- Falhas ao gravar histórico/lote executam compensação segura do saldo alterado.
- Página própria com abas Saldos, Movimentações e Lotes e validade.
- A movimentação permite ler o código de barras e preenche automaticamente o
  produto e a embalagem (unidade/fardo).
- Direção e motivo foram retirados do formulário; o motivo é derivado do tipo
  selecionado. O documento relacionado aparece como `Número da NF-e`.
- A movimentação oferece `Movimentar por: Unidade/Fardo`; Fardo só é habilitado
  quando o produto possui quantidade por fardo cadastrada.

## Compras

- Recebimento por fornecedor com múltiplos produtos em unidade ou fardo.
- Custos por embalagem convertidos para custo unitário com `Decimal`.
- Desconto, frete, NF-e, lote, validade, pagamento e vencimento.
- Entrada automática no estoque em unidades e atualização do último custo.
- Geração de conta a pagar para Boleto e A prazo.
- Numeração sequencial atômica no formato `CP-00000001`.
- Cancelamento de compra recebida com baixa controlada dos itens e cancelamento
  da conta a pagar ainda aberta.
- Falhas durante recebimento ou cancelamento executam compensações em ordem
  reversa e registram qualquer falha de compensação na auditoria.
- A compra só recebe status `Recebida` após estoque, custos e conta a pagar terem
  sido preparados.
- O cadastro não altera o saldo atual: produtos novos começam zerados e produtos
  existentes preservam seu saldo. Movimentações ficam no módulo de estoque.
- O cadastro permite informar a composição do fardo (por exemplo, 1 fardo = 12
  unidades), enquanto o estoque mínimo permanece sempre expresso em unidades.

## Requisitos

- Python 3.12 ou superior
- MongoDB 7 ou superior acessível pela rede local
- Windows 10/11 para o executável final

## Instalação

No PowerShell, a partir desta pasta:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edite `.env`. Em uma instalação de rede, use em `MONGODB_URI` o IP ou nome DNS
do computador que hospeda o MongoDB. Configure autenticação no servidor e não
versione o arquivo `.env`.

Exemplo de URI autenticada:

```text
mongodb://usuario:senha@192.168.1.10:27017/?authSource=admin
```

O MongoDB deve estar limitado à rede local pelo firewall e configurado para
escutar apenas nos endereços necessários. Cada computador executa a aplicação
com sua própria cópia do `.env`, apontando para o mesmo banco.

## Execução da infraestrutura

Com o MongoDB em execução:

```powershell
python main.py
```

O comando valida as configurações, prepara os índices e perfis, cria o primeiro
administrador quando necessário e abre a tela de login.

No primeiro acesso, o usuário é `admin`. Se `INITIAL_ADMIN_PASSWORD` estiver
vazio, uma senha forte é gerada e mostrada uma única vez. Se a variável for
preenchida, use uma senha com ao menos 10 caracteres, letras maiúscula e
minúscula, número e símbolo. Em ambos os casos, a troca no primeiro login é
obrigatória.

## Autenticação e RBAC

- Senhas são protegidas com Argon2id e nunca persistidas ou registradas em texto.
- Cinco falhas consecutivas bloqueiam a conta por 15 minutos.
- Usuários inativos e perfis inativos não autenticam.
- Login, falhas, bloqueios, logout, troca e redefinição de senha são auditados.
- Os perfis Administrador, Gerente, Caixa, Estoquista, Financeiro e Entregador
  são criados de modo idempotente.
- Liberações e bloqueios individuais são aplicados sobre o perfil; bloqueios
  individuais têm precedência.
- Todas as operações administrativas verificam permissões também no serviço.
- O administrador pode criar contas, ativar/inativar, redefinir senha temporária
  e editar exceções individuais de permissão.

## Testes

Testes unitários (não requerem MongoDB):

```powershell
pytest -m "not integration"
```

Teste de integração real, opcional:

```powershell
$env:TEST_MONGODB_URI = "mongodb://127.0.0.1:27017"
pytest -m integration
```

Cobertura local:

```powershell
pytest --cov=. --cov-report=term-missing --cov-report=html
```

## Executável Windows

O build usa o formato `onedir`, adequado às bibliotecas nativas do PySide6:

```powershell
.\build_windows.ps1
```

O resultado será `dist\AdegaDoBruninho\AdegaDoBruninho.exe`. Distribua a pasta
`AdegaDoBruninho` completa, não apenas o executável. Em cada computador, copie
`.env.example` para `.env` nessa pasta e configure a URI do MongoDB da rede.

Para atualizar uma estação, preserve o `.env` e substitua os demais arquivos.
Os dados comerciais permanecem centralizados no MongoDB.

O script executa automaticamente um `--smoke-test` após o empacotamento para
validar a inicialização do Qt e o carregamento dos recursos sem acessar o banco.

## Decisões de infraestrutura

- Datas retornadas pelo driver são conscientes de fuso (`tz_aware=True`) e as
  etapas de domínio persistirão datas em UTC.
- O `MongoClient` mantém pool thread-safe, apropriado para vários fluxos da
  aplicação. Cada computador possui seu pool, todos apontando para o servidor.
- A URI e senhas não são registradas; filtros removem credenciais acidentais.
- Configurações são imutáveis e validadas pelo Pydantic.
- Índices de módulos futuros serão adicionados junto dos respectivos modelos,
  evitando índices prematuros com regras ainda não aprovadas.
- Operações atômicas de estoque serão implementadas na Etapa 8, na camada de
  repositório, usando atualização condicional e transações quando disponíveis.

## Estrutura

O fluxo obrigatório será `View -> Service -> Repository -> MongoDB`. As pastas
dos módulos posteriores já existem, mas permanecem deliberadamente vazias até
a aprovação de cada etapa.

## Checklist manual das etapas 1 e 2

- [ ] Copiar `.env.example` para `.env` e preencher a URI.
- [ ] Executar `python main.py` com MongoDB ativo e confirmar código de saída 0.
- [ ] Confirmar a criação de `logs/distribuidora.log`.
- [ ] Confirmar no MongoDB os índices de `usuarios`, `auditoria` e
      `configuracoes`.
- [ ] Parar o MongoDB, executar novamente e confirmar mensagem segura e código 1.
- [ ] Usar URI inválida e confirmar erro de configuração sem exposição de senha.
- [ ] Executar os testes unitários e confirmar sucesso.
- [ ] Em outro computador da LAN, apontar para o mesmo servidor e validar o ping.
- [ ] Em banco vazio, abrir o sistema e anotar a senha temporária exibida.
- [ ] Entrar como `admin` e confirmar que a troca de senha não pode ser fechada.
- [ ] Tentar uma senha fraca e confirmar a mensagem da política de senha.
- [ ] Criar um usuário para cada perfil e confirmar a troca no primeiro acesso.
- [ ] Errar a senha cinco vezes e confirmar o bloqueio por 15 minutos.
- [ ] Inativar um usuário e confirmar que ele não consegue entrar.
- [ ] Bloquear individualmente uma permissão e confirmar que ela prevalece sobre
      o perfil.
- [ ] Entrar como usuário sem administração e confirmar que os botões protegidos
      não aparecem e que chamadas diretas ao serviço são negadas.
- [ ] Redefinir uma senha pelo administrador e confirmar a troca obrigatória.
- [ ] Confirmar os eventos correspondentes na coleção `auditoria`.
- [ ] Confirmar que o dashboard abre mesmo com as coleções comerciais vazias.
- [ ] Recolher e expandir o menu lateral em resolução pequena e grande.
- [ ] Alternar os temas, reiniciar e confirmar que a preferência foi mantida.
- [ ] Conferir nome e perfil na barra superior e testar o botão Sair.
- [ ] Alterar o período e cada filtro e confirmar a atualização dos gráficos.
- [ ] Conferir formatação `R$ 1.234,56` e datas `dd/MM/yyyy`.
- [ ] Inserir vendas de teste e comparar cards/gráficos com consultas no MongoDB.
- [ ] Entrar sem `dashboard.visualizar` e confirmar a negação pelo serviço.
- [ ] Confirmar que a aba principal aparece como `Painel`, não `Dashboard`.
- [ ] Cadastrar cliente apenas com nome e telefone.
- [ ] Cadastrar cliente completo com CPF válido, nascimento e endereço.
- [ ] Tentar CPF inválido e CPF duplicado e confirmar a recusa.
- [ ] Tentar confirmar maioridade para menor de 18 anos e confirmar a recusa.
- [ ] Adicionar, editar e remover endereços adicionais.
- [ ] Testar pesquisa por nome, CPF e telefone, além dos filtros de status.
- [ ] Testar páginas com 10, 20, 50 e 100 registros.
- [ ] Editar e inativar um cliente informando o motivo.
- [ ] Validar as permissões de clientes com Administrador, Gerente e Caixa.
- [ ] Conferir criação, alteração e inativação na coleção `auditoria`.
- [ ] Cadastrar fornecedores com CPF e com CNPJ válidos.
- [ ] Tentar cadastrar documento inválido ou duplicado e confirmar a recusa.
- [ ] Editar dados comerciais, endereço, condição de pagamento e status.
- [ ] Pesquisar por razão social, nome fantasia, CPF e CNPJ.
- [ ] Testar paginação e filtros de fornecedores ativos/inativos.
- [ ] Inativar fornecedor com motivo e conferir a auditoria.
- [ ] Conferir histórico de compras e últimos custos quando houver compras.
- [ ] Validar acesso como Administrador, Gerente, Estoquista e perfil sem acesso.
- [ ] Confirmar que Painel, Usuários, Clientes e Fornecedores não possuem emojis.
- [ ] Confirmar a criação automática das quinze categorias iniciais.
- [ ] Criar, editar e inativar uma categoria; testar nome duplicado.
- [ ] Cadastrar produto vendido apenas por unidade.
- [ ] Cadastrar produto com fardo, preços independentes e códigos diferentes.
- [ ] Tentar reutilizar um código de barras de unidade como fardo de outro produto.
- [ ] Conferir margem, promoções e formatação monetária brasileira.
- [ ] Conferir conversão visual de 93 unidades em 7 fardos e 9 unidades.
- [ ] Alterar preço e unidades por fardo e conferir eventos na auditoria.
- [ ] Testar pesquisa por nome, código, barras e marca e todos os filtros.
- [ ] Confirmar que Caixa não vê margem/custos nem botões administrativos.
- [ ] Confirmar que Estoquista não consegue alterar preços pelo serviço.
- [ ] Configurar um produto com 12 unidades por fardo e preço independente.
- [ ] Ler os códigos de unidade e fardo e conferir a modalidade identificada.
- [ ] Validar venda simulada de 2 fardos + 3 unidades como baixa de 27 unidades.
- [ ] Tentar vender fardo com menos unidades disponíveis e confirmar a recusa.
- [ ] Misturar linhas que isoladamente cabem, mas juntas excedem o saldo.
- [ ] Conferir devolução de 2 fardos como retorno de 24 unidades.
- [ ] Desativar a venda por fardo e confirmar que apenas unidade permanece válida.
- [ ] Conferir auditoria de composição e preço do fardo.
- [ ] Registrar entrada por unidade e por fardo e conferir a conversão.
- [ ] Registrar perda, avaria, vencimento, uso interno e bonificação.
- [ ] Tentar saída acima do saldo e confirmar que nenhum histórico é criado.
- [ ] Executar duas baixas concorrentes e confirmar que apenas uma usa o último saldo.
- [ ] Cadastrar lote com validade e conferir os quatro estados de alerta.
- [ ] Baixar saldo de lote específico e testar lote insuficiente.
- [ ] Realizar inventário acima e abaixo do saldo do sistema.
- [ ] Tentar permitir estoque negativo como Estoquista e confirmar a recusa.
- [ ] Autorizar saldo negativo como Administrador e conferir a auditoria.
- [ ] Conferir produto, embalagem, quantidade, conversão, saldos, usuário e motivo no histórico.
- [ ] Digitar o fornecedor e selecioná-lo nas sugestões da solicitação de compra.
- [ ] Digitar o produto, selecioná-lo nas sugestões e conferir categoria e preço de compra preenchidos automaticamente.
- [ ] Adicionar itens por unidade e por fardo e conferir a conversão apresentada no pedido.
- [ ] Confirmar que lote, validade, desconto e frete não aparecem na solicitação.
- [ ] Selecionar pagamento a prazo, informar `7/14/21` e conferir as três parcelas.
- [ ] Selecionar boleto e conferir o vencimento por calendário.
- [ ] Enviar o pedido, escolher a pasta e conferir o PDF `pedido_{fornecedor}-{número}.pdf` e a abertura do WhatsApp.
- [ ] Anexar o PDF na conversa e concluir manualmente o envio pelo WhatsApp.
- [ ] Confirmar o recebimento de um pedido enviado e verificar que o estoque não foi alterado.
- [ ] Ao receber, informar uma nota e depois várias notas separadas por linha, vírgula ou ponto e vírgula.
- [ ] Tentar repetir uma NF-e para o mesmo fornecedor e confirmar o bloqueio com indicação do pedido anterior.
- [ ] Usar a mesma numeração de NF-e para fornecedores diferentes e confirmar que é aceita.
- [ ] Selecionar uma compra e usar `Exibir NF-e` para conferir todas as notas vinculadas.
- [ ] Na aba Estoque, usar `Entrada de NF-e`, informar o pedido e conferir todas as notas e itens vinculados.
- [ ] Informar obrigatoriamente a validade de cada produto antes de concluir a entrada da NF-e.
- [ ] Confirmar a entrada de NF-e e somente então conferir a atualização do estoque e das contas a pagar.
- [ ] Após a entrada de NF-e, conferir o status `Concluído` na aba Compras.
- [ ] No PDV, localizar produto por nome, código interno ou código de barras.
- [ ] Digitar o código de barras e pressionar Enter; conferir produto e Unidade/Fardo preenchidos automaticamente.
- [ ] Digitar o nome no campo Produto, escolher a sugestão e adicionar sem usar uma caixa de seleção.
- [ ] Conferir a logo suavizada e centralizada como marca-d'água no carrinho do PDV em ambos os temas.
- [ ] Conferir que a logo lateral e a marca-d'água não exibem fundo retangular nos temas claro e escuro.
- [ ] Conferir o menu agrupado em Geral, Operação e Cadastros, com destaque dourado na tela ativa.
- [ ] Recolher o menu e confirmar que os títulos somem e os atalhos permanecem centralizados.
- [ ] Selecionar tema claro e escuro, sair e reiniciar; confirmar que o login mantém a última preferência.
- [ ] Entrar no sistema e confirmar que nenhuma página auxiliar pisca como janela independente.
- [ ] Conferir `Carregando sistema…` e uma única abertura maximizada, sem animação de opacidade ou janelas intermediárias.
- [ ] Confirmar que o menu e os botões permitidos aparecem normalmente, sem serem exibidos como janelas durante o login.
- [ ] Abrir o caixa com valor inicial e conferir o saldo esperado.
- [ ] Tentar abrir um segundo caixa para o mesmo usuário e confirmar o bloqueio.
- [ ] Registrar suprimento e sangria com motivo e conferir o novo saldo.
- [ ] Tentar finalizar venda sem caixa aberto e confirmar o bloqueio.
- [ ] Atingir R$ 500,00 no caixa e confirmar o aviso de sangria obrigatória no PDV.
- [ ] Tentar uma nova venda com R$ 500,00 ou mais no caixa e confirmar o bloqueio.
- [ ] Fazer uma sangria que deixe o saldo abaixo de R$ 500,00 e confirmar que o PDV foi liberado.
- [ ] Criar um pedido de entrega com cliente, telefone, endereço, produtos, volumes, pagamento e taxa.
- [ ] Atribuir um entregador e confirmar que ele visualiza somente as próprias entregas.
- [ ] Avançar o pedido por Pago, Em separação, Pronto para entrega, Saiu para entrega e Entregue.
- [ ] Tentar pular diretamente de Aguardando pagamento para Entregue e confirmar o bloqueio.
- [ ] Registrar uma ocorrência e conferir sua exibição nos detalhes do pedido.
- [ ] Conferir os horários de saída e entrega e os indicadores pendentes no Painel.
- [ ] Conferir no Financeiro as contas a pagar geradas pelas compras a prazo.
- [ ] Cadastrar uma despesa, uma receita e uma conta a receber.
- [ ] Registrar um pagamento parcial e conferir o saldo e o status `Parcial`.
- [ ] Quitar o saldo restante e conferir o status `Paga`.
- [ ] Tentar pagar acima do saldo e confirmar o bloqueio.
- [ ] Filtrar os lançamentos por tipo e status e conferir os totais do fluxo financeiro.
- [ ] Selecionar uma despesa aberta, editar seus dados e conferir a atualização.
- [ ] Excluir uma despesa informando o motivo e conferir que ela permanece no histórico como `Cancelada`.
- [ ] Após excluir uma despesa, confirmar que ela desaparece imediatamente da listagem padrão do Financeiro.
- [ ] Selecionar várias despesas com Ctrl/Shift, excluir em lote e conferir que todas desaparecem da lista.
- [ ] Gerar relatórios de vendas, estoque, compras, financeiro, entregas e caixas por período.
- [ ] Conferir totais e colunas na visualização antes da exportação.
- [ ] Exportar cada relatório para Excel e confirmar estilos, colunas e valores.
- [ ] Exportar cada relatório para PDF e confirmar cabeçalho, tabela e totalização.
- [ ] Pesquisar eventos na Auditoria por período, usuário, ação ou motivo.
- [ ] Alterar configurações operacionais e confirmar que dados críticos de conexão não ficam editáveis.
- [ ] Criar um backup ZIP e conferir manifesto, coleções e checksum.
- [ ] Tentar restaurar um arquivo inválido e confirmar que nenhum dado é alterado.
- [ ] Restaurar um backup válido como administrador digitando `RESTAURAR` e reiniciar o sistema.
- [ ] Tentar aplicar desconto total acima de 10% como caixa e confirmar a exigência de autorização.
- [ ] Repetir o desconto com gerente ou administrador e confirmar a liberação.
- [ ] Informar telefone inválido em pedido de entrega e confirmar a validação.
- [ ] Navegar por teclado e conferir o foco dourado em campos, botões e abas.
- [ ] Conferir seleção legível das tabelas nos temas claro e escuro.
- [ ] Tentar validar backup com coleção inesperada ou acima de 250 MB e confirmar o bloqueio.
- [ ] Confirmar que despesas pagas ou parcialmente pagas não podem ser editadas nem excluídas.
- [ ] Finalizar vendas em Dinheiro, Pix, Débito e Crédito e conferir os lançamentos.
- [ ] Fechar com valor contado igual ao esperado e depois com diferença justificada.
- [ ] Tentar fechar com diferença sem justificativa e confirmar o bloqueio.
- [ ] Conferir `Vendas do mês` como faturamento em reais e `Ticket médio` como receita dividida pelas vendas concluídas.
- [ ] Misturar unidades e fardos no carrinho e conferir a conversão do estoque.
- [ ] Aplicar desconto e acréscimo e conferir cálculos em reais.
- [ ] Finalizar com Dinheiro, Pix, Débito, Crédito e pagamento misto.
- [ ] Informar valor em dinheiro acima do total e conferir o troco.
- [ ] Tentar pagamento insuficiente e troco sem dinheiro e confirmar o bloqueio.
- [ ] Tentar vender acima do estoque e confirmar que a venda não é concluída.
- [ ] Registrar pagamento imediato e confirmar que não gera conta a pagar.
- [ ] Registrar boleto com vencimento e compra a prazo com parcelas e conferir as contas abertas.
- [ ] Confirmar atualização do custo unitário de cada produto.
- [ ] Cancelar compra com saldo disponível e conferir estorno e conta cancelada.
- [ ] Consumir parte do estoque e confirmar que cancelamento sem saldo é recusado.
- [ ] Simular falha no segundo item e conferir compensação do primeiro.
- [ ] Conferir eventos de recebimento, cancelamento e compensação na auditoria.

## Checklist — Controle de Fiado e Contas de Clientes

- [ ] Habilitar fiado para um cliente ativo, definir limite e conferir limite disponível.
- [ ] Tentar usar fiado sem cliente, com cliente inativo, desabilitado e bloqueado.
- [ ] Finalizar venda totalmente fiada e venda mista (Pix + Fiado).
- [ ] Repetir por unidade e por fardo e conferir a baixa correta do estoque.
- [ ] Tentar ultrapassar o limite e liberar somente com permissão e justificativa.
- [ ] Tentar vender para cliente inadimplente e conferir o bloqueio/autorização.
- [ ] Executar duas vendas simultâneas disputando o mesmo limite.
- [ ] Receber pagamento parcial, total e de várias contas pelas mais antigas.
- [ ] Conferir o movimento “Recebimento de fiado” separado das vendas no caixa.
- [ ] Estornar pagamento autorizado e conferir caixa, dívida, conta e extrato.
- [ ] Aplicar juros ou desconto e verificar justificativa e auditoria.
- [ ] Renegociar contas e conferir preservação das contas originais.
- [ ] Conferir os oito indicadores da tela Fiado e os seis indicadores do Painel.
- [ ] Gerar o relatório de fiado, validar faixas de atraso e exportar Excel/PDF.
- [ ] Confirmar que Estoquista e Entregador não acessam valores ou extratos.

## Checklist — Controle de Comandas

- [ ] Abrir comanda sem cliente usando apenas uma identificação.
- [ ] Abrir comanda vinculada e conferir nome e telefone preenchidos.
- [ ] Confirmar o alerta ao abrir outra comanda para o mesmo cliente.
- [ ] Abrir comandas simultaneamente e conferir números únicos sequenciais.
- [ ] Adicionar produto por código de barras de unidade e de fardo.
- [ ] Conferir conversão e reserva de dois fardos mais três unidades.
- [ ] Tentar reservar acima do disponível e confirmar o bloqueio.
- [ ] Remover item com motivo e conferir liberação da reserva.
- [ ] Cancelar comanda e confirmar que estoque físico e caixa não mudaram.
- [ ] Solicitar fechamento e confirmar bloqueio de edição.
- [ ] Finalizar em dinheiro, Pix e pagamento misto com caixa aberto.
- [ ] Finalizar parcialmente em fiado e conferir somente esse valor no contas a receber.
- [ ] Tentar fiado sem cliente cadastrado e confirmar a recusa.
- [ ] Repetir o fechamento e confirmar que não é criada uma segunda venda.
- [ ] Conferir baixa física e retirada da reserva ao finalizar.
- [ ] Conferir indicadores da tela Comandas e do Painel.
- [ ] Gerar conferência PDF antes e depois do fechamento.
- [ ] Gerar o relatório de comandas e exportar para Excel/PDF.
- [ ] Conferir permissões de Caixa, Gerente, Estoquista e Financeiro.
- [ ] Conferir auditoria de abertura, itens, fechamento, cancelamento e impressão.
