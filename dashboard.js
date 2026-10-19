const sourceDefinitions = [
  { id: 'djen', name: 'CNJ / DJEN', type: 'Fonte prioritaria', description: 'Comunicacoes do Diario de Justica Eletronico Nacional, consultadas por OAB, UF e periodo.', docs: 'https://hcomunicaapi.cnj.jus.br/swagger/index.html', real: true },
  { id: 'datajud', name: 'DataJud', type: 'Fonte prioritaria', description: 'Metadados e movimentacoes processuais publicas dos tribunais integrados ao CNJ.', docs: 'https://datajud-wiki.cnj.jus.br/api-publica/endpoints/', real: false },
  { id: 'dejt', name: 'DEJT', type: 'Fonte prioritaria', description: 'Antes de integrar, validar o servico/WSDL, o formato da consulta e a disponibilidade dos dados.', docs: 'https://dejt.jt.jus.br/dejt/dejt', real: false },
  { id: 'inlabs', name: 'DOU / INLABS', type: 'Fonte prioritaria', description: 'Disponibiliza arquivos diarios em XML/PDF; sera necessario baixar, ler e filtrar os arquivos pela OAB.', docs: 'https://inlabs.in.gov.br/acessar.php', real: false },
  { id: 'deoab', name: 'DEOAB', type: 'Fonte prioritaria', description: 'Portal de edicoes e publicacoes da OAB, sem API publica identificada para consumo direto.', docs: 'https://deoab.oab.org.br/', real: false },
  { id: 'aasp', name: 'AASP', type: 'Agregador recomendado', description: 'API de intimacoes para integrar publicacoes diretamente ao sistema do Peticiona.', docs: 'https://intimacaoapi.aasp.org.br/docapi/index.html', real: false },
];

const $ = (selector) => document.querySelector(selector);
const api = async (url, options = {}) => {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || data.error || `HTTP ${response.status}`);
  return data;
};

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[char]));
}

function dateDefaults() {
  const today = new Date();
  const firstOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
  const iso = (date) => date.toISOString().slice(0, 10);
  $('#data-inicio').value = iso(firstOfMonth);
  $('#data-fim').value = iso(today);
}

function statusLabel(status) {
  return ({ ok: 'Dados reais', credencial_necessaria: 'Chave pendente', documentada_para_validacao: 'Validacao tecnica', integracao_parcial: 'Integracao parcial', requer_cadastro_ou_download: 'Processamento necessario', portal_sem_api_confirmada: 'API nao confirmada', reachable: 'Portal acessivel', unavailable: 'Indisponivel', indisponivel: 'Indisponivel', erro_http: 'Erro HTTP', tribunal_nao_mapeado: 'Tribunal nao mapeado', processo_invalido: 'Processo invalido', sem_resultado: 'Sem resultado' }[status] || status || 'Nao testada');
}

function statusClass(status) {
  if (status === 'ok') return 'status-ok';
  if (status === 'credencial_necessaria' || status === 'requer_cadastro_ou_download') return 'status-warning';
  if (status === 'indisponivel' || status === 'erro_http' || status === 'unavailable') return 'status-danger';
  if (status === 'reachable' || status === 'integracao_parcial') return 'status-info';
  return 'status-neutral';
}

function renderSourceCards(config = {}, probes = {}) {
  const enabled = config.enabled_sources || { djen: true, aasp: true };
  const byName = Object.fromEntries((probes.fontes || []).map((item) => [item.id, item]));
  $('#source-grid').innerHTML = sourceDefinitions.map((source) => {
    const probe = byName[source.id] || {};
    const sourceStatus = source.id === 'djen' ? 'ok' : (probe.situacao || 'documentada_para_validacao');
    const checked = enabled[source.id] !== false;
    const realClass = source.real ? ' real' : '';
    return `<article class="source-card${checked ? ' enabled' : ''}${realClass}">
      <div class="source-card-head"><div><h3>${escapeHtml(source.name)}</h3><span class="type">${escapeHtml(source.type)}</span></div>
      <label class="switch" title="Ativar ${escapeHtml(source.name)}"><input type="checkbox" data-source="${source.id}" ${checked ? 'checked' : ''}><span class="slider"></span></label></div>
      <p>${escapeHtml(source.description)}</p>
      <div class="source-card-footer"><span class="status-badge ${statusClass(sourceStatus)}">${escapeHtml(statusLabel(sourceStatus))}</span><a href="${source.docs}" target="_blank" rel="noreferrer">Documentacao <span>&nearr;</span></a></div>
    </article>`;
  }).join('');
  const active = Object.values(enabled).filter(Boolean).length;
  $('#active-count').textContent = active;
  $('#aasp-credential-status').textContent = config.aasp_configured ? 'Configurada' : 'Pendente';
  $('#aasp-credential-status').className = `status-badge ${config.aasp_configured ? 'status-ok' : 'status-warning'}`;
}

async function loadConfig() {
  try {
    const [config, probes] = await Promise.all([api('/v1/config'), api('/v1/fontes?probe=true')]);
    window.currentConfig = config;
    window.currentProbes = probes;
    renderSourceCards(config, probes);
    $('#config-status').textContent = config.aasp_configured ? 'Configuracao carregada' : 'DJEN ativo | AASP pendente';
    $('#config-status').className = `status-badge ${config.aasp_configured ? 'status-ok' : 'status-warning'}`;
  } catch (error) {
    $('#config-status').textContent = 'Falha ao carregar';
    $('#config-status').className = 'status-badge status-danger';
    $('#save-message').textContent = error.message;
  }
}

async function saveConfig() {
  const enabledSources = {};
  document.querySelectorAll('[data-source]').forEach((input) => { enabledSources[input.dataset.source] = input.checked; });
  $('#save-message').textContent = 'Salvando...';
  try {
    const result = await api('/v1/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ aasp_chave: $('#aasp-key').value, aasp_codigo: $('#aasp-code').value, enabled_sources: enabledSources }) });
    $('#save-message').textContent = result.persisted ? 'Configuracao salva.' : 'Configuracao aplicada nesta execucao local.';
    $('#aasp-key').value = '';
    await loadConfig();
  } catch (error) { $('#save-message').textContent = `Nao foi possivel salvar: ${error.message}`; }
}

async function probeSources() {
  $('#probe-sources').textContent = 'Testando...';
  try { window.currentProbes = await api('/v1/fontes?probe=true'); renderSourceCards(window.currentConfig || {}, window.currentProbes); $('#save-message').textContent = 'Disponibilidade atualizada.'; }
  catch (error) { $('#save-message').textContent = error.message; }
  finally { $('#probe-sources').textContent = 'Testar disponibilidade'; }
}

function renderFindings(sourceResults = []) {
  const liveByName = Object.fromEntries(sourceResults.map((source) => [source.fonte, source]));
  const plannedSources = [
    { key: 'DJEN', label: 'DJEN', defaultStatus: 'documentada_para_validacao', defaultText: 'Consulta real habilitada por OAB, UF e periodo.' },
    { key: 'AASP', label: 'AASP', defaultStatus: 'credencial_necessaria', defaultText: 'Conector preparado; depende da chave oficial.' },
    { key: 'DataJud', label: 'DataJud', defaultStatus: 'integracao_parcial', defaultText: 'Consulta real por numero de processo habilitada; busca por OAB ainda nao e direta.' },
    { key: 'DEJT', label: 'DEJT', defaultStatus: 'documentada_para_validacao', defaultText: 'Validar o servico/WSDL, o formato da consulta e a disponibilidade dos dados antes de integrar.' },
    { key: 'DOU / INLABS', label: 'DOU / INLABS', defaultStatus: 'requer_cadastro_ou_download', defaultText: 'Disponibiliza XML/PDF; e necessario baixar, ler e filtrar os arquivos pela OAB.' },
    { key: 'DEOAB', label: 'DEOAB', defaultStatus: 'portal_sem_api_confirmada', defaultText: 'Portal disponivel, mas sem API publica identificada para consumo direto.' },
  ];
  $('#source-findings').innerHTML = plannedSources.map((planned) => {
    const source = liveByName[planned.key] || { fonte: planned.key, status: planned.defaultStatus, mensagem: planned.defaultText };
    const detail = source.status === 'ok' ? `${source.total ?? source.items?.length ?? 0} registro(s) retornado(s).` : (source.mensagem || planned.defaultText);
    return `<div class="finding"><div class="finding-head"><strong>${escapeHtml(planned.label)}</strong><span class="status-badge ${statusClass(source.status)}">${escapeHtml(statusLabel(source.status))}</span></div><p>${escapeHtml(detail)}</p></div>`;
  }).join('') || '<div class="empty-state">Nenhum status retornado.</div>';
}

function renderItems(items) {
  if (!items.length) { $('#results-body').innerHTML = '<tr><td colspan="6" class="empty-state">Nenhuma publicacao encontrada no periodo.</td></tr>'; return; }
  $('#results-body').innerHTML = items.slice(0, 200).map((item) => `<tr>
    <td class="source-cell">${escapeHtml(item.fonte || 'AASP')}</td>
    <td><strong>${escapeHtml(item.tribunal || item.orgao || '-')}</strong><br>${escapeHtml(item.orgao || '')}</td>
    <td>${escapeHtml(item.numero_processo || item.numeroProcesso || '-')}</td>
    <td>${escapeHtml(item.data_publicacao || item.dataDisponibilizacao || '-')}</td>
    <td>${escapeHtml(item.tipo || item.tipoComunicacao || '-')}</td>
    <td class="content-cell">${escapeHtml((item.texto || item.conteudo || item.descricao || '-').slice(0, 260))}${item.link ? `<br><a href="${escapeHtml(item.link)}" target="_blank" rel="noreferrer">Abrir publicacao &nearr;</a>` : ''}</td>
  </tr>`).join('');
}

function renderDatajud(result) {
  if (result.status !== 'ok') {
    $('#datajud-result').innerHTML = `<span class="status-badge ${statusClass(result.status)}">${escapeHtml(statusLabel(result.status))}</span><span style="margin-left:10px">${escapeHtml(result.mensagem || 'DataJud sem retorno.')}</span>`;
    $('#movements-body').innerHTML = '<tr><td colspan="3" class="empty-state">Nenhuma movimentacao retornada.</td></tr>';
    return;
  }
  $('#datajud-result').innerHTML = `<div class="summary-grid"><div><span>Processo</span><b>${escapeHtml(result.processo)}</b></div><div><span>Tribunal</span><b>${escapeHtml(result.tribunal)}</b></div><div><span>Classe</span><b>${escapeHtml(result.classe || '-')}</b></div><div><span>Orgao</span><b>${escapeHtml(result.orgao_julgador || '-')}</b></div><div><span>Movimentacoes</span><b>${escapeHtml(result.total_movimentos)}</b></div><div><span>Atualizacao</span><b>${escapeHtml(result.ultima_atualizacao || '-')}</b></div></div>`;
  const movements = result.movimentos || [];
  $('#movements-body').innerHTML = movements.length ? movements.map((movement) => `<tr><td>${escapeHtml(movement.data || '-')}</td><td><strong>${escapeHtml(movement.nome || '-')}</strong></td><td>${escapeHtml(movement.orgao || '-')}</td></tr>`).join('') : '<tr><td colspan="3" class="empty-state">O processo foi localizado, mas nao possui movimentacoes retornadas.</td></tr>';
}

async function loadDatajud() {
  const processo = encodeURIComponent($('#datajud-processo').value);
  const tribunal = encodeURIComponent($('#datajud-tribunal').value);
  $('#datajud-query').textContent = 'Consultando DataJud...';
  $('#datajud-query').disabled = true;
  $('#datajud-result').innerHTML = '<span class="status-badge status-info">Consultando</span><span style="margin-left:10px">A API publica do DataJud pode levar alguns segundos para responder.</span>';
  try {
    const result = await api(`/v1/datajud?processo=${processo}&tribunal=${tribunal}`);
    renderDatajud(result);
  } catch (error) {
    $('#datajud-result').innerHTML = `<span class="status-badge status-danger">Falha</span><span style="margin-left:10px">${escapeHtml(error.message)}</span>`;
  } finally {
    $('#datajud-query').textContent = 'Consultar movimentacoes';
    $('#datajud-query').disabled = false;
  }
}

async function loadResults() {
  const oab = encodeURIComponent($('#oab').value || '196088');
  const uf = encodeURIComponent($('#uf').value || 'SP');
  const inicio = encodeURIComponent($('#data-inicio').value);
  const fim = encodeURIComponent($('#data-fim').value);
  $('#run-query').textContent = 'Consultando...';
  $('#results-notice').innerHTML = '<strong>Consultando fontes</strong><span>Aguarde enquanto o conector consulta o DJEN e verifica a AASP configurada.</span>';
  try {
    const query = `/v1/publicacoes?oab=${oab}&uf=${uf}&data_inicio=${inicio}&data_fim=${fim}`;
    const [result, processes] = await Promise.all([api(query), api(`/v1/processos?oab=${oab}&uf=${uf}&data_inicio=${inicio}&data_fim=${fim}`)]);
    $('#result-total').textContent = result.total;
    $('#process-total').textContent = processes.total;
    const working = (result.fontes || []).filter((source) => source.status === 'ok');
    $('#result-source').textContent = working.length ? working.map((source) => source.fonte).join(' + ') : 'Nenhuma';
    $('#query-period').textContent = `${result.data_inicio} a ${result.data_fim} | ${result.mock ? 'mock' : 'dados reais'}`;
    renderFindings(result.fontes || []);
    renderItems(result.items || []);
    const sample = (result.items || []).find((item) => item.tribunal === 'TJSP' && item.numero_processo) || (result.items || []).find((item) => item.numero_processo);
    if (sample) {
      $('#datajud-processo').value = sample.numero_processo;
      $('#datajud-tribunal').value = sample.tribunal || 'TJSP';
    }
    const sourceErrors = (result.fontes || []).filter((source) => source.status !== 'ok');
    if (result.mock) {
      $('#results-notice').innerHTML = '<strong>Modo mock</strong><span>Esta resposta usa dados de teste. Remova o parametro modo=mock para consultar as fontes reais.</span>';
      $('#results-notice').className = 'notice notice-blue';
    } else if (sourceErrors.length) {
      const details = sourceErrors.map((source) => `${source.fonte}: ${source.mensagem || statusLabel(source.status)}`).join(' | ');
      $('#results-notice').innerHTML = `<strong>Consulta parcial</strong><span>Uma ou mais fontes nao responderam. ${escapeHtml(details)}. Os registros das fontes disponiveis continuam exibidos.</span>`;
      $('#results-notice').className = 'notice notice-warning';
    } else {
      $('#results-notice').innerHTML = '<strong>Consulta concluida</strong><span>Os registros abaixo vieram das fontes indicadas na primeira coluna. A chave AASP continua pendente se ela nao estiver configurada.</span>';
      $('#results-notice').className = 'notice notice-blue';
    }
  } catch (error) {
    $('#results-notice').innerHTML = `<strong>Falha na consulta</strong><span>${escapeHtml(error.message)}</span>`;
    $('#results-notice').className = 'notice notice-danger';
  } finally { $('#run-query').textContent = 'Consultar agora'; }
}

function showView(view) {
  document.querySelectorAll('.view').forEach((element) => element.classList.toggle('active-view', element.id === `view-${view}`));
  document.querySelectorAll('.nav-item').forEach((element) => element.classList.toggle('active', element.dataset.view === view));
  if (view === 'results') loadResults();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

document.addEventListener('DOMContentLoaded', () => {
  dateDefaults();
  loadConfig();
  document.querySelectorAll('.nav-item').forEach((button) => button.addEventListener('click', () => showView(button.dataset.view)));
  $('#open-results').addEventListener('click', () => showView('results'));
  $('#back-config').addEventListener('click', () => showView('config'));
  $('#save-config').addEventListener('click', saveConfig);
  $('#probe-sources').addEventListener('click', probeSources);
  $('#run-query').addEventListener('click', loadResults);
  $('#datajud-query').addEventListener('click', loadDatajud);
});
