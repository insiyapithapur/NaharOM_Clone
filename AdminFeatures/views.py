from datetime import datetime
import os
from django.utils import timezone
import json
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from UserFeatures import models
from django.utils import timezone
from django.db import transaction
import base64
import time
from django.conf import settings
import hashlib

@csrf_exempt
def LoginAPI(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            mobile = data.get('mobile')
            password = data.get('password')

            if not mobile or not password:
                return JsonResponse({"message": "mobile and password are required"}, status=400)

            try:
                user = models.User.objects.get(mobile=mobile)
                if user.check_password(password):
                    if user.is_admin:
                        return JsonResponse({"message": "Admin logged in successfully", "id": user.id}, status=200)
                    else:
                        return JsonResponse({"message": "User is not an admin"}, status=403)
                else:
                    return JsonResponse({"message": "Invalid credentials"}, status=401)
            except models.User.DoesNotExist:
                return JsonResponse({"message": "Invalid credentials"}, status=401)

        except json.JSONDecodeError:
            return JsonResponse({"message": "Invalid JSON"}, status=400)
        except Exception as e:
            return JsonResponse({"message": str(e)}, status=500)
    else:
        return JsonResponse({"message": "Only POST method is allowed"}, status=405)
    
@csrf_exempt
def ExtractInvoicesAPI(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            if not isinstance(data, list):
                return JsonResponse({"message": "Invalid input format, expected a list of objects"}, status=400)

            filtered_invoices = []

            for company in data:
                invoices = company.get('invoices', [])
                for invoice in invoices:
                    if invoice.get('product') is not None:
                        filtered_invoices.append(invoice)
            
            return JsonResponse({"filtered_invoices": filtered_invoices}, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"message": "Invalid JSON"}, status=400)
        except Exception as e:
            return JsonResponse({"message": str(e)}, status=500)
    else:
        return JsonResponse({"message": "Only POST methods are allowed"}, status=405)

with open(os.path.join(os.path.dirname(__file__), 'invoices.json')) as f:
    invoices_data = json.load(f)

def filter_invoice_data(invoice):
    product = invoice.get('product', {})
    # print("product: ",product)
    return {
        "primary_invoice_id": invoice['id'],
        # hyperlink attach karvani che j dashboard open kare invoice no primary mathi
        "buyer_poc_name" : invoice['buyer_poc_name'],
        "product_name": product.get('name'),
        "irr": product.get('interest_rate_fixed'),
        "tenure_in_days": product.get('tenure_in_days'),
        "interest_rate" : product.get('interest_rate'),
        "xirr" : product.get('xirr_in_percentage'),
        "principle_amt" : product.get('principle_amt'),
        "expiration_time" : timezone.now() + timezone.timedelta(days=product.get('tenure_in_days')),
        "type" : "unfractionalized"
    }

@csrf_exempt
def GetInvoicesAPI(request, user_id, primary_invoice_id=None):
    if request.method == 'GET':
        try:
            if not user_id:
                return JsonResponse({"message": "user_id is required"}, status=400)

            try:
                user = models.User.objects.get(id=user_id)
            except models.User.DoesNotExist:
                return JsonResponse({"message": "User not found"}, status=404)

            if not user.is_admin:
                return JsonResponse({"message": "For this operation you have to register yourself with admin role"}, status=403)

            if primary_invoice_id:
                invoice_data = next((inv for inv in invoices_data['filtered_invoices'] if inv['id'] == primary_invoice_id), None)
                if not invoice_data:
                    return JsonResponse({"message": "Invoice not found"}, status=404)
                filtered_invoice_data = filter_invoice_data(invoice_data)
                return JsonResponse(filtered_invoice_data, status=200)
            else:
                filtered_invoices_data = [filter_invoice_data(inv) for inv in invoices_data['filtered_invoices']]
                return JsonResponse(filtered_invoices_data, safe=False, status=200)
            
        except json.JSONDecodeError:
            return JsonResponse({"message": "Invalid JSON"}, status=400)
        except Exception as e:
            return JsonResponse({"message": str(e)}, status=500)
    else:
        return JsonResponse({"message": "Only GET methods are allowed"}, status=405)
    
@csrf_exempt
def InvoiceAPI(request,user_id, primary_invoice_id=None):
    if request.method == 'GET':
        try:
            try:
                user = models.User.objects.get(id=user_id)
            except models.User.DoesNotExist:
                return JsonResponse({"message": "User not found"}, status=404)

            if not user.is_admin:
                return JsonResponse({"message": "For this operation you have to register yourself with admin role"}, status=403)

            if primary_invoice_id:
                invoice_data = next((inv for inv in invoices_data['filtered_invoices'] if inv['id'] == primary_invoice_id), None)
                if not invoice_data:
                    return JsonResponse({"message": "Invoice not found"}, status=404)
                filtered_invoice_data = filter_invoice_data(invoice_data)
                return JsonResponse(filtered_invoice_data, status=200)
            else:
                filtered_invoices_data = [filter_invoice_data(inv) for inv in invoices_data['filtered_invoices']]
                print(filter_invoice_data)
                fractionalized_invoice_data = models.Invoices.objects.all().values()
                for invoice in fractionalized_invoice_data:
                    invoice['type'] = "fractionalized"  
                combined_data = filtered_invoices_data + list(fractionalized_invoice_data)
                return JsonResponse(combined_data, safe=False, status=200)
        except json.JSONDecodeError:
            return JsonResponse({"message": "Invalid JSON"}, status=400)
        except Exception as e:
            return JsonResponse({"message": str(e)}, status=500)
    else:
        return JsonResponse({"message": "Only POST methods are allowed"}, status=405)

@csrf_exempt
def PostInvoiceAPI(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')

            if not user_id:
                return JsonResponse({"message": "user_id is required"}, status=400)

            try:
                user = models.User.objects.get(id=user_id)
            except models.User.DoesNotExist:
                return JsonResponse({"message": "User not found"}, status=404)

            if not user.is_admin:
                return JsonResponse({"message": "For this operation you have to register yourself with admin role"}, status=403)
            
            primary_invoice_id = data.get('primary_invoice_id')
            no_of_fractional_units = data.get('no_of_fractional_Unit')

            invoice_data = next((inv for inv in invoices_data['filtered_invoices'] if inv['id'] == primary_invoice_id), None)

            if not invoice_data or not invoice_data.get('product'):
                return JsonResponse({"message": "Invoice data not found or product is null"}, status=404)

            product_data = invoice_data['product']
            post_date = timezone.now().date()
            post_time = timezone.now().time()
            name = product_data['name']
            interest_rate = product_data['interest_rate']
            xirr = product_data['xirr_in_percentage']
            irr = product_data['interest_rate_fixed']
            tenure_in_days = product_data['tenure_in_days']
            principle_amt = product_data['principle_amt']
            expiration_time = timezone.now() + timezone.timedelta(days=tenure_in_days)

            if not all([primary_invoice_id, no_of_fractional_units]):
                return JsonResponse({"message": "All fields are required"}, status=400)
            
            with transaction.atomic():
                print("before create")
                # already posted case check
                invoice = models.Invoices.objects.create(
                    primary_invoice_id=primary_invoice_id,
                    no_of_partitions=no_of_fractional_units,
                    name=name,
                    post_date=post_date,
                    post_time=post_time,
                    post_date_time = timezone.now(),
                    interest= interest_rate,
                    xirr=xirr,
                    irr = irr ,
                    tenure_in_days=tenure_in_days,
                    principle_amt=principle_amt,
                    expiration_time=expiration_time,
                    remaining_partitions = no_of_fractional_units ,
                    sold = False
                )
                print("after create")

                fractional_units = [
                    models.FractionalUnits(invoice=invoice)
                    for _ in range(no_of_fractional_units)
                ]
                models.FractionalUnits.objects.bulk_create(fractional_units)

            return JsonResponse({"message": "Invoice created successfully", "Secondary_invoice_id": invoice.id}, status=201)

        except json.JSONDecodeError:
            return JsonResponse({"message": "Invalid JSON"}, status=400)
        except Exception as e:
            return JsonResponse({"message": str(e)}, status=500)
    else:
        return JsonResponse({"message": "Only POST methods are allowed"}, status=405)
    
@csrf_exempt
def SalesPurchasedReportAPI(request,User_id):
    if request.method == 'GET':
        try:
            # data = json.loads(request.body)
            # User_id = data.get('user_id')

            if not User_id:
                return JsonResponse({"message": "User_id is required"}, status=400)
            
            try:
                user = models.User.objects.get(id=User_id)
            except models.User.DoesNotExist:
                return JsonResponse({"message": "User not found"}, status=404)

            if not user.is_admin:
                return JsonResponse({"message": "For this operation you have to register yourself with admin role"}, status=403)
            
            with transaction.atomic():
                try:
                    sales_purchase_reports = models.SalePurchaseReport.objects.all()
                    report_list = []
                    for report in sales_purchase_reports:

                        try:
                            pan_card_no = models.PanCardNos.objects.get(user_role=report.buyer.user).pan_card_no
                            seller_pan_card_no = models.PanCardNos.objects.get(user_role = report.seller.user).pan_card_no
                        except models.PanCardNos.DoesNotExist:
                            pan_card_no = None
                            seller_pan_card_no = None

                        # purchase_datetimet = datetime.combine(report.buyer.purchase_date, report.buyer.purchase_time)
                        # purchase_datetime = timezone.make_aware(purchase_datetimet, timezone.get_default_timezone())
                        # print(purchase_datetime)
                        # print(timezone.now())
                        # print(report.buyer.purchase_date, "  ",report.buyer.purchase_time)
                        try:
                            credited_transaction = models.OutstandingBalanceTransaction.objects.get(
                                wallet = report.seller.wallet,
                                time_date="2024-07-02 18:16:09.123273+00"
                            )
                            print(credited_transaction)
                            credited_amount = credited_transaction.creditedAmount
                        except models.OutstandingBalanceTransaction.DoesNotExist:
                            credited_amount = None

                        seller_info = {}
                        if report.seller.User.role == 'individual':
                            individual_details = models.IndividualDetails.objects.get(user_role=report.seller.User)
                            seller_info = {
                                'first_name': individual_details.first_name,
                                'last_name': individual_details.last_name,
                            }
                        elif report.seller.User.role == 'company':
                            company_details = models.CompanyDetails.objects.get(user_role=report.seller.User)
                            seller_info = {
                                'company_name': company_details.company_name,
                            }

                        report_data = {
                            'id': report.id,
                            'purchaser_Info' :{
                                'purchaser_id' : report.buyer.id,
                                'purchased_units' : report.buyer.no_of_partitions,
                                'purchased_Date' : report.buyer.purchase_date,
                                'purchaser_pan_card_no': pan_card_no,
                                'purchaser_name' : {
                                    'user' : report.buyer.user.user.mobile
                                }
                             },
                            'seller_info': {
                                "Value_of_Per_Unit" : ( report.seller.amount ) / (report.seller.no_of_partitions),
                                'sell_Date' : report.seller.sell_date,
                                'Name_of_Co.': seller_info,
                                'Pan_Card_No' : seller_pan_card_no,
                                'total_amt_credited': credited_amount, #error
                            },
                        }
                        report_list.append(report_data)

                    return JsonResponse({"sales_purchase_reports": report_list}, status=200)

                except models.SalePurchaseReport.DoesNotExist:
                    return JsonResponse({"message": "SalePurchaseReport not found"}, status=404)
                # return JsonResponse({"sales_purchase_report" : sales_purchase_report},status=200)
        except json.JSONDecodeError:
            return JsonResponse({"message": "Invalid JSON"}, status=400)
        except Exception as e:
            return JsonResponse({"message": str(e)}, status=500)

    else:
        return JsonResponse({"message": "Only POST methods are allowed"}, status=405)
    
@csrf_exempt
def UserManagementAPI(request):
    if request.method == 'GET':
        try:
            users = models.User.objects.all()
            all_user_details = []

            for user in users:
                print(user.mobile)
                try:
                    user_role = models.UserRole.objects.get(user=user)
                    print(user.id)
                    user_details = {
                        "user_id": user.id,
                        "user_role": user_role.role,
                        "email": user.email,
                        "date_of_joining": user.created_at,
                    }

                    if user_role.role == 'Company':
                        # company_details = models.CompanyDetails.objects.get(user_role=user_role)
                        user_details.update({
                            # "company_name": company_details.company_name,
                            "company_name": "ABC",
                        })
                    elif user_role.role == 'Individual':
                        # individual_details = models.IndividualDetails.objects.get(user_role=user_role)
                        user_details.update({
                            # "first_name": individual_details.first_name,
                            # "last_name": individual_details.last_name,
                            "first_name": "First name",
                            "last_name": "last name",
                        })
                        
                    try:
                        # pan_card = models.PanCardNos.objects.get(user_role=user_role)
                        user_details["pan_card_no"] = "dekkf cvk f"
                    except models.PanCardNos.DoesNotExist:
                        user_details["pan_card_no"] = "43245mdmd"

                    # permissions = {s
                    #     "is_admin": user.is_admin,
                    #     "is_staff": user.is_staff,
                    #     "is_active": user.is_active
                    # }
                    user_details["is_admin"] = user.is_admin

                    all_user_details.append(user_details)

                except models.UserRole.DoesNotExist:
                    continue  
                except models.CompanyDetails.DoesNotExist:
                    continue  
                except models.IndividualDetails.DoesNotExist:
                    continue  

            return JsonResponse(all_user_details, safe=False, status=200)

        except Exception as e:
            return JsonResponse({"message": str(e)}, status=500)
    else:
        return JsonResponse({"message": "Only GET methods are allowed"}, status=405)

def generate_token(admin_id, user_id):
    timestamp = int(time.time())
    token = f"{admin_id}:{user_id}:{timestamp}"
    signature = hashlib.sha256(f"{token}:{settings.SECRET_KEY}".encode()).hexdigest()
    token_with_signature = f"{token}:{signature}"
    encoded_token = base64.urlsafe_b64encode(token_with_signature.encode()).decode()
    return encoded_token

def decode_token(token):
    try:
        decoded_token = base64.urlsafe_b64decode(token.encode()).decode()
        parts = decoded_token.split(':')
        if len(parts) != 4:
            return None
        
        admin_id, user_id, timestamp, received_signature = parts
        token_without_signature = f"{admin_id}:{user_id}:{timestamp}"
        expected_signature = hashlib.sha256(f"{token_without_signature}:{settings.SECRET_KEY}".encode()).hexdigest()
        
        if received_signature != expected_signature:
            return None
        
        return admin_id, user_id, int(timestamp)
    except Exception as e:
        return "failed to decode the token"
    
@csrf_exempt
def GenerateTokenAPI(request, admin_id, user_id):
    if request.method == 'GET':
        token = generate_token(admin_id, user_id)
        # admin_id , user_id exist check?
        return JsonResponse({"token": token}, status=200)
    else:
        return JsonResponse({"message": "Only GET methods are allowed"}, status=405)
    
@csrf_exempt
def UserPersonateAPI(request):
    token = request.GET.get('token')
    if not token:
        return JsonResponse({"message": "Token is required"}, status=400)

    decoded_data = decode_token(token)
    if not decoded_data:
        return JsonResponse({"message": "Invalid token"}, status=400)

    admin_id, user_id, timestamp = decoded_data

    try:
        admin = models.User.objects.get(id=admin_id, is_superuser=True)
    except models.User.DoesNotExist:
        return JsonResponse({"message": "Admin not found or not authorized"}, status=403)

    try:
        user = models.User.objects.get(id=user_id)
    except models.User.DoesNotExist:
        return JsonResponse({"message": "User not found"}, status=404)

    # Here you can include the logic to fetch and return the user dashboard data
    user_dashboard_data = {
        "user_id": user.id,
        "user_email": user.email,
        # Add other user-specific data here
    }
    return JsonResponse(user_dashboard_data, status=200)