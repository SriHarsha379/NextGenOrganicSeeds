def generate_upi_payment_link(user, amount):
    upi_id = "merchant@upi"  # Replace with your UPI ID
    upi_link = f"upi://pay?pa={upi_id}&pn={user.username}&mc=&tid=&tr=&tn=Seed+Purchase&am={amount}&cu=INR"
    return upi_link
