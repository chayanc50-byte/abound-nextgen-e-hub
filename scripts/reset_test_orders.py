#!/usr/bin/env python3
"""Remove test orders and dependent sales data while preserving users/products.

This script is intentionally reusable:
- it deletes the selected orders (all orders by default),
- removes commissions tied to those orders,
- restores product stock from the removed order quantities,
- recalculates wallets from the remaining active commission records.

It does not delete users, products, categories, notifications, referral IDs,
or referral hierarchy relationships.
"""
import os
import sys
from collections import defaultdict


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from app import ActivityLog, Commission, Order, Product, Wallet


def _active_commission_total(user_id):
    total = (
        db.session.query(db.func.coalesce(db.func.sum(Commission.commission_amount), 0))
        .filter(
            Commission.user_id == user_id,
            Commission.status != "reversed",
        )
        .scalar()
    )
    return float(total or 0)


def reset_test_orders():
    with app.app_context():
        summary = {
            "orders_deleted": 0,
            "commission_records_deleted": 0,
            "wallets_recalculated": 0,
            "products_restocked": 0,
            "notifications_removed": 0,
            "activity_logs_removed": 0,
        }

        try:
            orders = Order.query.all()
            order_ids = [order.id for order in orders]
            summary["orders_deleted"] = len(order_ids)

            print(f"Orders that will be deleted: {summary['orders_deleted']}")
            confirmation = input("Type YES to proceed with cleanup: ")
            if confirmation != "YES":
                print("Cleanup cancelled. No data was modified.")
                return

            restock_by_product_id = defaultdict(int)
            for order in orders:
                quantity = order.quantity or 1
                restock_by_product_id[order.product_id] += quantity

            if order_ids:
                summary["commission_records_deleted"] = Commission.query.filter(
                    Commission.order_id.in_(order_ids)
                ).delete(synchronize_session=False)

                summary["activity_logs_removed"] = ActivityLog.query.filter(
                    ActivityLog.target_type == "order",
                    ActivityLog.target_id.in_(order_ids),
                ).delete(synchronize_session=False)

                Order.query.filter(Order.id.in_(order_ids)).delete(
                    synchronize_session=False
                )

            for product_id, quantity in restock_by_product_id.items():
                product = Product.query.get(product_id)
                if not product or product.stock_quantity is None:
                    continue
                product.stock_quantity = (product.stock_quantity or 0) + quantity
                summary["products_restocked"] += 1

            for wallet in Wallet.query.all():
                recalculated_total = _active_commission_total(wallet.user_id)
                wallet.total_earnings = recalculated_total
                wallet.available_balance = recalculated_total
                summary["wallets_recalculated"] += 1

            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        print("Test order cleanup complete.")
        print(f"Orders deleted: {summary['orders_deleted']}")
        print(
            "Commission records deleted: "
            f"{summary['commission_records_deleted']}"
        )
        print(f"Wallets recalculated: {summary['wallets_recalculated']}")
        print(f"Products restocked: {summary['products_restocked']}")
        print(f"Notifications removed: {summary['notifications_removed']}")
        print(f"Activity logs removed: {summary['activity_logs_removed']}")


if __name__ == "__main__":
    reset_test_orders()
