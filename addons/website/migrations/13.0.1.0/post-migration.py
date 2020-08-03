# Copyright 2020 Payam Yasaie <https://www.tashilgostar.com>
# Copyright 2020 ForgeFlow <https://www.forgeflow.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from openupgradelib import openupgrade


def fill_website_rewrite_name(env):
    openupgrade.logged_query(
        env.cr, """
        UPDATE website_rewrite
        SET name = CASE WHEN url_from IS NOT NULL OR url_to IS NOT NULL THEN
            url_from || ' -> ' || url_to
            ELSE 'default_name' END
        WHERE name IS NULL""",
    )


@openupgrade.migrate()
def migrate(env, version):
    fill_website_rewrite_name(env)
    openupgrade.load_data(env.cr, 'website', 'migrations/13.0.1.0/noupdate_changes.xml')
