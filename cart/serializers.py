from rest_framework import serializers


class QuantityField(serializers.Field):
    def to_internal_value(self, value):
        if type(value) is not int or not 1 <= value <= 99:
            raise serializers.ValidationError('تعداد باید عدد صحیح بین ۱ و ۹۹ باشد.')
        return value

    def to_representation(self, value):
        return value


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError('بدنهٔ درخواست باید یک شیء JSON باشد.')
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: 'این فیلد مجاز نیست.' for key in unknown})
        return super().to_internal_value(data)


class AddItemSerializer(StrictSerializer):
    product_id = serializers.IntegerField(min_value=1)
    variant_id = serializers.IntegerField(min_value=1, allow_null=True, required=False, default=None)
    quantity = QuantityField()
    request_id = serializers.UUIDField()


class UpdateItemSerializer(StrictSerializer):
    quantity = QuantityField()
