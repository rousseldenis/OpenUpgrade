# Copyright 2020 Payam Yasaie <https://www.tashilgostar.com>
# Copyright 2020 ForgeFlow <https://www.forgeflow.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from openupgradelib import openupgrade

_unlink_by_xmlid = [
    # account.journal
    'point_of_sale.pos_sale_journal',
    # ir.sequence
    'point_of_sale.seq_picking_type_posout',
]


def fill_pos_config_default_cashbox_id(env):
    openupgrade.logged_query(
        env.cr, """
        UPDATE pos_config pc
        SET default_cashbox_id = absc.id
        FROM account_cashbox_line acl
        JOIN account_bank_statement_cashbox absc ON acl.cashbox_id = absc.id
        WHERE acl.{} = pc.id
        """.format(openupgrade.get_legacy_name('default_pos_id'))
    )


def fill_pos_config_amount_authorized_diff(env):
    openupgrade.logged_query(
        env.cr, """
        UPDATE pos_config pc
        SET amount_authorized_diff = aj.{amount}
        FROM account_bank_statement abs
        JOIN account_journal aj ON abs.journal_id = aj.id
        JOIN pos_session ps ON abs.pos_session_id = ps.id
        WHERE ps.config_id = pc.id AND pc.amount_authorized_diff IS NULL
            AND aj.{amount} IS NOT NULL
        """.format(amount=openupgrade.get_legacy_name('amount_authorized_diff'))
    )


def fill_pos_session_move_id(env):
    openupgrade.logged_query(
        env.cr, """
        UPDATE pos_session ps
        SET move_id = po.{move}
        FROM pos_order po
        WHERE po.session_id = ps.id AND po.{move} IS NOT NULL
            AND ps.move_id IS NULL AND ps.state = 'closed'
        """.format(move=openupgrade.get_legacy_name('account_move'))
    )


def fill_pos_order_account_move(env):
    openupgrade.logged_query(
        env.cr, """
        UPDATE pos_order po
        SET account_move = am.id
        FROM account_invoice ai
        JOIN account_move am ON am.old_invoice_id = ai.id
        WHERE po.{} = ai.id
        """.format(openupgrade.get_legacy_name('invoice_id'))
    )


def fill_pos_config_barcode_nomenclature_id(env):
    openupgrade.logged_query(
        env.cr, """
        UPDATE pos_config pc
        SET barcode_nomenclature_id = rc.nomenclature_id
        FROM res_company rc
        WHERE pc.company_id = rc.id AND pc.barcode_nomenclature_id IS NULL
        """,
    )


def fill_pos_config_module_pos_hr(env):
    if openupgrade.table_exists(env.cr, 'hr_employee'):
        openupgrade.logged_query(
            env.cr, """
            UPDATE pos_config SET module_pos_hr = TRUE""",
        )


def delete_pos_order_line_with_empty_order_id(env):
    openupgrade.logged_query(
        env.cr, "DELETE FROM pos_order_line WHERE order_id IS NULL",
    )


def fill_stock_warehouse_pos_type_id(env):
    warehouses = env['stock.warehouse'].search([('pos_type_id', '=', False)])
    for warehouse in warehouses:
        all_used_colors = [res['color'] for res in env[
            'stock.picking.type'].search_read(
            [('warehouse_id', '!=', False), ('color', '!=', False)],
            ['color'], order='color')]
        available_colors = [
            zef for zef in range(0, 12) if zef not in all_used_colors]
        color = available_colors[0] if available_colors else 0
        sequence = env['ir.sequence'].sudo().create({
            'name': warehouse.name + ' ' + 'Picking POS',
            'prefix': warehouse.code + '/POS/',
            'padding': 5,
            'company_id': warehouse.company_id.id,
        })
        pos_type = env['stock.picking.type'].create({
            'name': 'PoS Orders',
            'code': 'outgoing',
            'default_location_src_id': warehouse.lot_stock_id.id,
            'default_location_dest_id': env.ref(
                'stock.stock_location_customers').id,
            'sequence': sequence.id,
            'sequence_code': 'POS',
            'company_id': warehouse.company_id.id,
            'warehouse_id': warehouse.id,
            'color': color,
        })
        warehouse.write({'pos_type_id': pos_type.id})


def create_pos_payment_methods(env):
    env.cr.execute("""
        SELECT DISTINCT journal_id
        FROM pos_config_journal_rel
    """)
    journal_ids = [aj[0] for aj in env.cr.fetchall()]
    if journal_ids:
        vals_list = []
        for journal in env['account.journal'].browse(journal_ids):
            vals = {
                'name': 'Cash',
                'cash_journal_id': journal.id,
                'is_cash_count': True,
                'company_id': journal.company_id.id,
            }
            vals_list += [vals]
        env['pos.payment.method'].create(vals_list)
    openupgrade.logged_query(
        env.cr, """
        INSERT INTO pos_config_pos_payment_method_rel
            (pos_config_id, pos_payment_method_id)
        SELECT pos_config_id, ppm.id
        FROM pos_config_journal_rel pcjr
        JOIN account_journal aj ON pcjr.journal_id = aj.id
        JOIN pos_payment_method ppm ON ppm.cash_journal_id = aj.id""")


def create_pos_payments(env):
    env.cr.execute("""
        SELECT DISTINCT absl.id, ppm.id
        FROM account_bank_statement abs
        JOIN pos_session ps ON abs.pos_session_id = ps.id
        JOIN account_bank_statement_line absl ON absl.statement_id = abs.id
        LEFT JOIN account_journal aj ON abs.journal_id = aj.id
        JOIN pos_payment_method ppm ON ppm.cash_journal_id = aj.id
    """)
    st_lines_ids_dict = {stl[0]: stl[1] for stl in env.cr.fetchall()}
    if st_lines_ids_dict:
        vals_list = []
        for st_line in env['account.bank.statement.line'].browse(
                list(st_lines_ids_dict)):
            vals = {
                'name': st_line.name,
                'pos_order_id': st_line.pos_statement_id.id,
                'amount': st_line.amount,
                'payment_method_id': st_lines_ids_dict[st_line.id],
                'payment_date': st_line.create_date,
            }
            vals_list += [vals]
        env['pos.payment'].create(vals_list)


@openupgrade.migrate()
def migrate(env, version):
    fill_pos_config_default_cashbox_id(env)
    fill_pos_config_amount_authorized_diff(env)
    fill_pos_session_move_id(env)
    fill_pos_order_account_move(env)
    fill_pos_config_barcode_nomenclature_id(env)
    fill_pos_config_module_pos_hr(env)
    delete_pos_order_line_with_empty_order_id(env)
    fill_stock_warehouse_pos_type_id(env)
    create_pos_payment_methods(env)
    create_pos_payments(env)
    openupgrade.delete_records_safely_by_xml_id(env, _unlink_by_xmlid)
    openupgrade.load_data(env.cr, 'point_of_sale', 'migrations/13.0.1.0.1/noupdate_changes.xml')
