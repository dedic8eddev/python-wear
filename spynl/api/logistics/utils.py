PACKING_LIST_DOWNLOAD_FIELDS = {
    field: 1
    for field in [
        'orderNumber',
        'type',
        'customReference',
        'customer.name',
        'customer.address.address',
        'customer.address.zipcode',
        'customer.address.city',
        'customer.address.country',
        'products.articleCode',
        'products.articleDescription',
        'products.localizedPrice',
        'products.localizedSuggestedRetailPrice',
        'products.skus.barcode',
        'products.skus.qty',
        'products.skus.size',
        'products.skus.colorCode',
        'products.skus.colorDescription',
    ]
}


def generate_list_of_skus(order):
    """
    Make a list wherein each sku gets it's own line (all upper dict values are copied)
    """
    result = []
    base_order = {key: value for key, value in order.items() if key != 'products'}
    for product in order.get('products', []):
        base_product = {key: value for key, value in product.items() if key != 'skus'}
        for sku in product.get('skus', []):
            result.append({**base_order, **base_product, **sku})
    return result
