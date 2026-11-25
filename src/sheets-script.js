// Trigger en Apps Script — notifica al grupo de Gmail cuando la
// Cloud Function registra un archivo nuevo en el Sheet.
//
// Por qué onChange y no onEdit:
//   - onEdit simple solo se dispara cuando un usuario edita en la UI.
//   - La Cloud Function escribe con la API de Sheets, eso NO dispara onEdit.
//
// Columnas del Sheet (Sheet1):
//   A ID | B Nombre | C Tamaño bytes | D Tipo | E Notificado
//

const GROUP_EMAIL = 'administracion@agenda-master.com.mx';
const SHEET_NAME = 'Hoja 1';
const COL_NOTIFICADO = 5;

function onChange(e) {
  if (e && e.changeType && e.changeType !== 'INSERT_ROW' && e.changeType !== 'EDIT') {
    return;
  }
  revisarNuevosArchivos();
}

function revisarNuevosArchivos() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const hoja = ss.getSheetByName(SHEET_NAME);
  const lastRow = hoja.getLastRow();
  if (lastRow < 2) return;

  const rows = hoja.getRange(2, 1, lastRow - 1, COL_NOTIFICADO).getValues();
  const pendientes = [];

  rows.forEach((row, i) => {
    const notificado = row[COL_NOTIFICADO - 1];
    if (!notificado || String(notificado).toLowerCase() === 'no') {
      pendientes.push({ rowNum: i + 2, data: row });
    }
  });

  if (pendientes.length === 0) return;

  // Un solo correo por ejecución, con todos los archivos nuevos.
  let body = 'Archivos nuevos registrados en el bucket:\n\n';
  pendientes.forEach(p => {
    const d = p.data;
    body += `ID ${d[0]} — ${d[1]}\n`;
    body += `  Tamaño: ${d[2]} bytes | Tipo: ${d[3]}\n`;
  });

  GmailApp.sendEmail(
    GROUP_EMAIL,
    `[Bucket] ${pendientes.length} archivo(s) nuevo(s) registrado(s)`,
    body
  );

  // Marcar como notificados para no duplicar el correo.
  pendientes.forEach(p => {
    hoja.getRange(p.rowNum, COL_NOTIFICADO).setValue('Sí');
  });
}
